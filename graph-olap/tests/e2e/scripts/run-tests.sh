#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E2E_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(git rev-parse --show-toplevel)"

# Parse arguments
CLUSTER=""
EXEC="local"
NOTEBOOK=""
WORKERS="auto"

while [[ $# -gt 0 ]]; do
    case $1 in
        --cluster=*) CLUSTER="${1#*=}" ;;
        --exec=*) EXEC="${1#*=}" ;;
        --notebook=*) NOTEBOOK="${1#*=}" ;;
        --workers=*) WORKERS="${1#*=}" ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

# Validate CLUSTER is provided
if [[ -z "$CLUSTER" ]]; then
    echo "ERROR: CLUSTER is required"
    echo "Usage: $0 --cluster=orbstack|gke-london [--exec=local|job|jupyter] [--notebook=<name>]"
    exit 1
fi

# Load cluster configuration
CLUSTER_FILE="$E2E_DIR/clusters/${CLUSTER}.env"
if [[ ! -f "$CLUSTER_FILE" ]]; then
    echo "ERROR: Unknown cluster '$CLUSTER'"
    echo "Available: $(ls -1 "$E2E_DIR/clusters/" 2>/dev/null | sed 's/.env$//' | tr '\n' ' ')"
    exit 1
fi

# Export cluster config
set -a
source "$CLUSTER_FILE"
set +a

# Switch to correct kubectl context if specified
if [[ -n "${KUBE_CONTEXT:-}" ]]; then
    CURRENT_CONTEXT=$(kubectl config current-context 2>/dev/null || echo "")
    if [[ "$CURRENT_CONTEXT" != "$KUBE_CONTEXT" ]]; then
        echo "Switching kubectl context: $CURRENT_CONTEXT → $KUBE_CONTEXT"
        if ! kubectl config use-context "$KUBE_CONTEXT" &>/dev/null; then
            echo "ERROR: Failed to switch to context '$KUBE_CONTEXT'"
            echo "Available contexts: $(kubectl config get-contexts -o name | tr '\n' ' ')"
            exit 1
        fi
    fi
fi

# Load persona tokens from Kubernetes Secret (single source of truth)
SECRET_NAME="e2e-persona-tokens"
NAMESPACE="${GRAPH_OLAP_NAMESPACE:-graph-olap-local}"

echo "Loading persona tokens from K8s secret $SECRET_NAME in namespace $NAMESPACE"
if ! kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" &>/dev/null; then
    echo "ERROR: Secret '$SECRET_NAME' not found in namespace '$NAMESPACE'"
    echo ""
    echo "Create the secret:"
    echo "  cd tools/local-dev && ./scripts/generate-e2e-tokens.sh"
    exit 1
fi

# Export all keys from the secret as environment variables
eval "$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o json | \
    jq -r '.data | to_entries[] | "export \(.key)=\(.value | @base64d)"')"

# E2E Cleanup API function - cleans up all test resources via control-plane API
call_cleanup_api() {
    local phase="$1"  # "PRE-TEST" or "POST-TEST"

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "E2E Cleanup: $phase"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Use OPS_DAVE persona for cleanup (has ops role)
    if [[ -z "${GRAPH_OLAP_API_KEY_OPS_DAVE:-}" ]]; then
        echo "WARNING: GRAPH_OLAP_API_KEY_OPS_DAVE not set, skipping API cleanup"
        return 0
    fi

    local cleanup_url="${GRAPH_OLAP_API_URL}/api/admin/e2e-cleanup"
    local response
    local http_code

    # Call cleanup API with 5-minute timeout
    response=$(curl -sf -X DELETE --max-time 300 \
        -H "Authorization: Bearer $GRAPH_OLAP_API_KEY_OPS_DAVE" \
        -H "Content-Type: application/json" \
        -w "\n%{http_code}" \
        "$cleanup_url" 2>&1) || true

    # Extract HTTP code (last line) and body (everything else)
    http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')

    if [[ "$http_code" == "200" ]]; then
        echo "Cleanup successful:"
        echo "$body" | jq '.data' 2>/dev/null || echo "$body"
    elif [[ "$http_code" == "401" || "$http_code" == "403" ]]; then
        echo "WARNING: Cleanup API returned $http_code (auth failed), continuing..."
    else
        echo "WARNING: Cleanup API returned $http_code, continuing..."
        echo "$body" | head -5
    fi
    echo ""
}

# Build pytest args
PYTEST_ARGS="-v"
if [[ -n "$NOTEBOOK" ]]; then
    # Run specific notebook test
    # Extract test function name from notebook name (e.g., 03_managing_resources -> test_03)
    TEST_NUM=$(echo "$NOTEBOOK" | grep -oE '^[0-9]+')
    if [[ -z "$TEST_NUM" ]]; then
        echo "ERROR: Invalid notebook name '$NOTEBOOK'"
        echo "Notebook names must start with a number (e.g., 04_cypher_basics)"
        exit 1
    fi
    PYTEST_ARGS="$PYTEST_ARGS -k test_${TEST_NUM}"
else
    # All tests - use parallel execution with configurable workers
    PYTEST_ARGS="$PYTEST_ARGS -n $WORKERS --dist=loadgroup"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "E2E Test Runner"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Cluster:  $CLUSTER ($GRAPH_OLAP_API_URL)"
echo "  Exec:     $EXEC"
echo "  Notebook: ${NOTEBOOK:-all}"
echo "  Workers:  $WORKERS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Execute based on method
case "$EXEC" in
    local)
        # Run pre-flight checks for local OrbStack
        if [[ "$CLUSTER" == "orbstack" && "${VALIDATE_DEPLOYMENT:-false}" == "true" ]]; then
            if [[ -f "$REPO_ROOT/tools/local-dev/scripts/validate-test-freshness.sh" ]]; then
                "$REPO_ROOT/tools/local-dev/scripts/validate-test-freshness.sh"
            fi
        fi

        # PRE-TEST cleanup via API (cleans all E2E test user resources)
        call_cleanup_api "PRE-TEST"

        # Legacy cleanup for orphaned resources (kept for backwards compatibility)
        if [[ -f "$REPO_ROOT/tools/local-dev/scripts/cleanup-test-resources.py" ]]; then
            python3 "$REPO_ROOT/tools/local-dev/scripts/cleanup-test-resources.py" || true
        fi

        # Run tests and capture exit code
        TEST_EXIT=0
        cd "$E2E_DIR" && pytest tests/ $PYTEST_ARGS || TEST_EXIT=$?

        # POST-TEST cleanup (only on success to preserve state for debugging failures)
        if [[ $TEST_EXIT -eq 0 ]]; then
            call_cleanup_api "POST-TEST"
        else
            echo ""
            echo "Tests failed (exit $TEST_EXIT) - skipping POST-TEST cleanup to preserve state"
            echo "Run cleanup manually: curl -X DELETE -H 'Authorization: Bearer \$GRAPH_OLAP_API_KEY_OPS_DAVE' ${GRAPH_OLAP_API_URL}/api/admin/e2e-cleanup"
        fi

        exit $TEST_EXIT
        ;;
    job)
        "$SCRIPT_DIR/exec-job.sh" --cluster="$CLUSTER" --pytest-args="$PYTEST_ARGS"
        ;;
    jupyter)
        "$SCRIPT_DIR/exec-jupyter.sh" --cluster="$CLUSTER" --pytest-args="$PYTEST_ARGS"
        ;;
    *)
        echo "ERROR: Unknown exec method '$EXEC'"
        echo "Available: local, job, jupyter"
        exit 1
        ;;
esac

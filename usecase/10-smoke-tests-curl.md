# Smoke Tests and Curl Examples

This guide provides ready-to-use curl commands and smoke test scripts for validating the Graph OLAP platform deployment.

## 1. Environment Setup

```bash
# Set base variables
export API_URL="http://control-plane.graph-olap.svc.cluster.local:8080"
export EXTERNAL_URL="https://graph-olap.internal.your-domain.com"
export NAMESPACE="graph-olap"
export TEST_USER="testuser@example.com"
export TEST_ROLE="analyst"
```

## 2. Health Check Smoke Tests

### Basic Health Check

```bash
# In-cluster health check
curl -s "$API_URL/health" | jq .

# Expected response:
# {"status": "healthy", "version": "1.0.0"}
```

### Readiness Check

```bash
# Check if service is ready to accept traffic
curl -s "$API_URL/ready" | jq .

# Expected response:
# {"status": "ready", "database": "connected", "k8s": "connected"}
```

### Full Health Check Script

```bash
#!/bin/bash
# smoke-health.sh - Health check smoke test

set -e

API_URL="${API_URL:-http://control-plane.graph-olap.svc.cluster.local:8080}"

echo "=== Health Check Smoke Test ==="
echo "API URL: $API_URL"
echo ""

# Test 1: Health endpoint
echo "[1/3] Testing /health..."
HEALTH=$(curl -sf "$API_URL/health")
if echo "$HEALTH" | jq -e '.status == "healthy"' > /dev/null; then
    echo "✓ Health check passed"
else
    echo "✗ Health check failed: $HEALTH"
    exit 1
fi

# Test 2: Ready endpoint
echo "[2/3] Testing /ready..."
READY=$(curl -sf "$API_URL/ready")
if echo "$READY" | jq -e '.status == "ready"' > /dev/null; then
    echo "✓ Ready check passed"
else
    echo "✗ Ready check failed: $READY"
    exit 1
fi

# Test 3: API info
echo "[3/3] Testing /api/..."
API_INFO=$(curl -sf "$API_URL/api/")
if echo "$API_INFO" | jq -e '.version' > /dev/null; then
    echo "✓ API info check passed"
    echo "  Version: $(echo "$API_INFO" | jq -r '.version')"
else
    echo "✗ API info check failed: $API_INFO"
    exit 1
fi

echo ""
echo "=== All health checks passed! ==="
```

## 3. Authentication Smoke Tests

### In-Cluster Header Auth

```bash
# Test with X-Username and X-User-Role headers
curl -s "$API_URL/api/instances" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE" | jq .
```

### JWT Bearer Token Auth

```bash
# Test with JWT token (external access)
curl -s "$EXTERNAL_URL/api/instances" \
    -H "Authorization: Bearer $JWT_TOKEN" | jq .
```

### Auth Smoke Test Script

```bash
#!/bin/bash
# smoke-auth.sh - Authentication smoke test

set -e

API_URL="${API_URL:-http://control-plane.graph-olap.svc.cluster.local:8080}"
TEST_USER="${TEST_USER:-testuser@example.com}"
TEST_ROLE="${TEST_ROLE:-analyst}"

echo "=== Authentication Smoke Test ==="
echo "User: $TEST_USER"
echo "Role: $TEST_ROLE"
echo ""

# Test 1: No auth (should fail)
echo "[1/3] Testing without auth (should fail)..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/instances")
if [ "$HTTP_CODE" == "401" ] || [ "$HTTP_CODE" == "403" ]; then
    echo "✓ Correctly rejected unauthenticated request ($HTTP_CODE)"
else
    echo "✗ Expected 401/403, got $HTTP_CODE"
    exit 1
fi

# Test 2: Valid auth
echo "[2/3] Testing with valid auth..."
RESPONSE=$(curl -sf "$API_URL/api/instances" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE")
if [ $? -eq 0 ]; then
    echo "✓ Authenticated request succeeded"
else
    echo "✗ Authenticated request failed"
    exit 1
fi

# Test 3: Check user context
echo "[3/3] Testing user context endpoint..."
USER_INFO=$(curl -sf "$API_URL/api/me" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE" 2>/dev/null || echo '{}')
if echo "$USER_INFO" | jq -e '.email' > /dev/null 2>&1; then
    echo "✓ User context retrieved"
    echo "  Email: $(echo "$USER_INFO" | jq -r '.email')"
else
    echo "⚠ User context endpoint not available (optional)"
fi

echo ""
echo "=== Authentication tests passed! ==="
```

## 4. API Endpoint Smoke Tests

### List Mappings

```bash
curl -s "$API_URL/api/mappings" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE" | jq .
```

### List Snapshots

```bash
curl -s "$API_URL/api/snapshots" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE" | jq .
```

### List Instances

```bash
curl -s "$API_URL/api/instances" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE" | jq .
```

### API Endpoints Smoke Test Script

```bash
#!/bin/bash
# smoke-api.sh - API endpoints smoke test

set -e

API_URL="${API_URL:-http://control-plane.graph-olap.svc.cluster.local:8080}"
TEST_USER="${TEST_USER:-testuser@example.com}"
TEST_ROLE="${TEST_ROLE:-analyst}"

AUTH_HEADERS="-H \"X-Username: $TEST_USER\" -H \"X-User-Role: $TEST_ROLE\""

echo "=== API Endpoints Smoke Test ==="
echo ""

ENDPOINTS=(
    "GET /api/"
    "GET /api/mappings"
    "GET /api/snapshots"
    "GET /api/instances"
)

PASSED=0
FAILED=0

for ENDPOINT in "${ENDPOINTS[@]}"; do
    METHOD=$(echo "$ENDPOINT" | cut -d' ' -f1)
    PATH=$(echo "$ENDPOINT" | cut -d' ' -f2)

    echo -n "Testing $METHOD $PATH... "

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -X "$METHOD" "$API_URL$PATH" \
        -H "X-Username: $TEST_USER" \
        -H "X-User-Role: $TEST_ROLE")

    if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
        echo "✓ ($HTTP_CODE)"
        ((PASSED++))
    else
        echo "✗ ($HTTP_CODE)"
        ((FAILED++))
    fi
done

echo ""
echo "=== Results: $PASSED passed, $FAILED failed ==="

if [ $FAILED -gt 0 ]; then
    exit 1
fi
```

## 5. Instance Lifecycle Smoke Test

### Create Instance

```bash
# Create a new instance
curl -s -X POST "$API_URL/api/instances" \
    -H "Content-Type: application/json" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE" \
    -d '{
        "snapshot_id": 1,
        "wrapper_type": "ryugraph"
    }' | jq .

# Save instance ID
INSTANCE_ID=$(curl -s -X POST "$API_URL/api/instances" \
    -H "Content-Type: application/json" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE" \
    -d '{"snapshot_id": 1, "wrapper_type": "ryugraph"}' | jq -r '.id')

echo "Created instance: $INSTANCE_ID"
```

### Get Instance Status

```bash
# Check instance status
curl -s "$API_URL/api/instances/$INSTANCE_ID" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE" | jq .
```

### Wait for Instance Ready

```bash
# Poll until instance is running
while true; do
    STATUS=$(curl -s "$API_URL/api/instances/$INSTANCE_ID" \
        -H "X-Username: $TEST_USER" \
        -H "X-User-Role: $TEST_ROLE" | jq -r '.status')

    echo "Status: $STATUS"

    if [ "$STATUS" == "running" ]; then
        echo "Instance is ready!"
        break
    elif [ "$STATUS" == "failed" ]; then
        echo "Instance failed to start"
        exit 1
    fi

    sleep 5
done
```

### Delete Instance

```bash
# Delete the instance
curl -s -X DELETE "$API_URL/api/instances/$INSTANCE_ID" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE"

echo "Instance deleted"
```

### Full Lifecycle Smoke Test Script

```bash
#!/bin/bash
# smoke-lifecycle.sh - Instance lifecycle smoke test

set -e

API_URL="${API_URL:-http://control-plane.graph-olap.svc.cluster.local:8080}"
TEST_USER="${TEST_USER:-testuser@example.com}"
TEST_ROLE="${TEST_ROLE:-analyst}"
SNAPSHOT_ID="${SNAPSHOT_ID:-1}"
WRAPPER_TYPE="${WRAPPER_TYPE:-ryugraph}"
TIMEOUT="${TIMEOUT:-300}"

echo "=== Instance Lifecycle Smoke Test ==="
echo "Snapshot ID: $SNAPSHOT_ID"
echo "Wrapper Type: $WRAPPER_TYPE"
echo "Timeout: ${TIMEOUT}s"
echo ""

# Step 1: Create instance
echo "[1/5] Creating instance..."
CREATE_RESPONSE=$(curl -sf -X POST "$API_URL/api/instances" \
    -H "Content-Type: application/json" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE" \
    -d "{\"snapshot_id\": $SNAPSHOT_ID, \"wrapper_type\": \"$WRAPPER_TYPE\"}")

INSTANCE_ID=$(echo "$CREATE_RESPONSE" | jq -r '.id')
echo "✓ Created instance: $INSTANCE_ID"

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up instance $INSTANCE_ID..."
    curl -sf -X DELETE "$API_URL/api/instances/$INSTANCE_ID" \
        -H "X-Username: $TEST_USER" \
        -H "X-User-Role: $TEST_ROLE" || true
    echo "Cleanup complete"
}
trap cleanup EXIT

# Step 2: Wait for running status
echo "[2/5] Waiting for instance to be running..."
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    INSTANCE=$(curl -sf "$API_URL/api/instances/$INSTANCE_ID" \
        -H "X-Username: $TEST_USER" \
        -H "X-User-Role: $TEST_ROLE")

    STATUS=$(echo "$INSTANCE" | jq -r '.status')

    if [ "$STATUS" == "running" ]; then
        echo "✓ Instance is running (took ${ELAPSED}s)"
        break
    elif [ "$STATUS" == "failed" ]; then
        echo "✗ Instance failed to start"
        exit 1
    fi

    echo "  Status: $STATUS (${ELAPSED}s)"
    sleep 5
    ((ELAPSED+=5))
done

if [ $ELAPSED -ge $TIMEOUT ]; then
    echo "✗ Timeout waiting for instance"
    exit 1
fi

# Step 3: Get wrapper URL
echo "[3/5] Getting wrapper URL..."
WRAPPER_URL=$(echo "$INSTANCE" | jq -r '.url')
echo "✓ Wrapper URL: $WRAPPER_URL"

# Step 4: Test wrapper health
echo "[4/5] Testing wrapper health..."
if [ "$WRAPPER_URL" != "null" ] && [ -n "$WRAPPER_URL" ]; then
    WRAPPER_HEALTH=$(curl -sf "$WRAPPER_URL/health" || echo '{"status": "unknown"}')
    if echo "$WRAPPER_HEALTH" | jq -e '.status' > /dev/null 2>&1; then
        echo "✓ Wrapper health check passed"
    else
        echo "⚠ Wrapper health check returned unexpected response"
    fi
else
    echo "⚠ Wrapper URL not available (in-cluster mode)"
fi

# Step 5: Test query (optional)
echo "[5/5] Testing query..."
if [ "$WRAPPER_URL" != "null" ] && [ -n "$WRAPPER_URL" ]; then
    QUERY_RESULT=$(curl -sf -X POST "$WRAPPER_URL/query" \
        -H "Content-Type: application/json" \
        -H "X-Username: $TEST_USER" \
        -H "X-User-Role: $TEST_ROLE" \
        -d '{"query": "MATCH (n) RETURN count(n) as count"}' || echo '{}')

    if echo "$QUERY_RESULT" | jq -e '.results' > /dev/null 2>&1; then
        echo "✓ Query executed successfully"
        echo "  Result: $(echo "$QUERY_RESULT" | jq -c '.results')"
    else
        echo "⚠ Query returned unexpected response"
    fi
else
    echo "⚠ Skipping query test (no wrapper URL)"
fi

echo ""
echo "=== Lifecycle smoke test passed! ==="
```

## 6. Wrapper Query Smoke Tests

### Basic Count Query

```bash
curl -s -X POST "$WRAPPER_URL/query" \
    -H "Content-Type: application/json" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE" \
    -d '{"query": "MATCH (n) RETURN count(n) as node_count"}' | jq .
```

### Node Query

```bash
curl -s -X POST "$WRAPPER_URL/query" \
    -H "Content-Type: application/json" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE" \
    -d '{"query": "MATCH (n) RETURN n LIMIT 5"}' | jq .
```

### Relationship Query

```bash
curl -s -X POST "$WRAPPER_URL/query" \
    -H "Content-Type: application/json" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE" \
    -d '{"query": "MATCH (a)-[r]->(b) RETURN type(r), count(r) as count ORDER BY count DESC LIMIT 10"}' | jq .
```

### Query with Parameters

```bash
curl -s -X POST "$WRAPPER_URL/query" \
    -H "Content-Type: application/json" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE" \
    -d '{
        "query": "MATCH (n) WHERE n.name = $name RETURN n",
        "parameters": {"name": "Example"}
    }' | jq .
```

### Query Smoke Test Script

```bash
#!/bin/bash
# smoke-query.sh - Wrapper query smoke test

set -e

WRAPPER_URL="${WRAPPER_URL:-http://wrapper-test.graph-olap.svc.cluster.local:8000}"
TEST_USER="${TEST_USER:-testuser@example.com}"
TEST_ROLE="${TEST_ROLE:-analyst}"

echo "=== Query Smoke Test ==="
echo "Wrapper URL: $WRAPPER_URL"
echo ""

# Test 1: Wrapper health
echo "[1/4] Testing wrapper health..."
HEALTH=$(curl -sf "$WRAPPER_URL/health")
echo "✓ Wrapper is healthy"

# Test 2: Node count
echo "[2/4] Testing node count query..."
RESULT=$(curl -sf -X POST "$WRAPPER_URL/query" \
    -H "Content-Type: application/json" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE" \
    -d '{"query": "MATCH (n) RETURN count(n) as count"}')
COUNT=$(echo "$RESULT" | jq -r '.results[0].count // .results[0][0] // "unknown"')
echo "✓ Node count: $COUNT"

# Test 3: Edge count
echo "[3/4] Testing edge count query..."
RESULT=$(curl -sf -X POST "$WRAPPER_URL/query" \
    -H "Content-Type: application/json" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE" \
    -d '{"query": "MATCH ()-[r]->() RETURN count(r) as count"}')
COUNT=$(echo "$RESULT" | jq -r '.results[0].count // .results[0][0] // "unknown"')
echo "✓ Edge count: $COUNT"

# Test 4: Sample data
echo "[4/4] Testing sample data query..."
RESULT=$(curl -sf -X POST "$WRAPPER_URL/query" \
    -H "Content-Type: application/json" \
    -H "X-Username: $TEST_USER" \
    -H "X-User-Role: $TEST_ROLE" \
    -d '{"query": "MATCH (n) RETURN labels(n)[0] as label, count(n) as count ORDER BY count DESC LIMIT 5"}')
echo "✓ Sample data retrieved"
echo "$RESULT" | jq '.results'

echo ""
echo "=== Query smoke tests passed! ==="
```

## 7. Full Smoke Test Suite

```bash
#!/bin/bash
# smoke-all.sh - Run all smoke tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================"
echo "     Graph OLAP Full Smoke Test        "
echo "========================================"
echo ""

# Configuration
export API_URL="${API_URL:-http://control-plane.graph-olap.svc.cluster.local:8080}"
export TEST_USER="${TEST_USER:-testuser@example.com}"
export TEST_ROLE="${TEST_ROLE:-analyst}"

echo "Configuration:"
echo "  API_URL: $API_URL"
echo "  TEST_USER: $TEST_USER"
echo "  TEST_ROLE: $TEST_ROLE"
echo ""

TESTS=(
    "Health Checks:smoke-health.sh"
    "Authentication:smoke-auth.sh"
    "API Endpoints:smoke-api.sh"
    "Instance Lifecycle:smoke-lifecycle.sh"
)

PASSED=0
FAILED=0

for TEST in "${TESTS[@]}"; do
    NAME=$(echo "$TEST" | cut -d':' -f1)
    SCRIPT=$(echo "$TEST" | cut -d':' -f2)

    echo "========================================"
    echo "Running: $NAME"
    echo "========================================"

    if [ -f "$SCRIPT_DIR/$SCRIPT" ]; then
        if bash "$SCRIPT_DIR/$SCRIPT"; then
            echo "✓ $NAME PASSED"
            ((PASSED++))
        else
            echo "✗ $NAME FAILED"
            ((FAILED++))
        fi
    else
        echo "⚠ Script not found: $SCRIPT"
        ((FAILED++))
    fi

    echo ""
done

echo "========================================"
echo "           SMOKE TEST RESULTS          "
echo "========================================"
echo "  Passed: $PASSED"
echo "  Failed: $FAILED"
echo "========================================"

if [ $FAILED -gt 0 ]; then
    echo "Some tests failed!"
    exit 1
else
    echo "All tests passed!"
    exit 0
fi
```

## 8. Quick One-Liner Tests

### From kubectl (In-Cluster)

```bash
# Health check
kubectl run smoke --rm -it --image=curlimages/curl --restart=Never -- \
    curl -sf http://control-plane.graph-olap.svc.cluster.local:8080/health

# List instances
kubectl run smoke --rm -it --image=curlimages/curl --restart=Never -- \
    curl -sf http://control-plane.graph-olap.svc.cluster.local:8080/api/instances \
    -H "X-Username: test@example.com" -H "X-User-Role: analyst"

# Create instance
kubectl run smoke --rm -it --image=curlimages/curl --restart=Never -- \
    curl -sf -X POST http://control-plane.graph-olap.svc.cluster.local:8080/api/instances \
    -H "Content-Type: application/json" \
    -H "X-Username: test@example.com" -H "X-User-Role: analyst" \
    -d '{"snapshot_id":1,"wrapper_type":"ryugraph"}'
```

### Using httpie (Alternative to curl)

```bash
# Health check
http GET $API_URL/health

# List instances with auth
http GET $API_URL/api/instances \
    X-Username:$TEST_USER \
    X-User-Role:$TEST_ROLE

# Create instance
http POST $API_URL/api/instances \
    X-Username:$TEST_USER \
    X-User-Role:$TEST_ROLE \
    snapshot_id:=1 \
    wrapper_type=ryugraph
```

## 9. Troubleshooting Failed Tests

### Check Pod Status

```bash
kubectl get pods -n graph-olap -o wide
```

### Check Logs

```bash
# Control plane logs
kubectl logs -n graph-olap -l app=control-plane -c control-plane --tail=100

# Wrapper logs
kubectl logs -n graph-olap -l wrapper-type --tail=100
```

### Check Events

```bash
kubectl get events -n graph-olap --sort-by='.lastTimestamp' | tail -20
```

### Debug Network

```bash
kubectl run debug --rm -it --image=nicolaka/netshoot --restart=Never -- \
    nslookup control-plane.graph-olap.svc.cluster.local
```

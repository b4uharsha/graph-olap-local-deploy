#!/usr/bin/env bash
# Remove all Graph OLAP local deployment resources.
set -euo pipefail

NAMESPACE="${1:-graph-olap-local}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}    $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $1"; }

echo "Removing Graph OLAP local deployment (namespace: $NAMESPACE)..."
echo ""

helm uninstall graph-olap -n "$NAMESPACE" 2>/dev/null && ok "Uninstalled graph-olap" || warn "graph-olap not installed"
helm uninstall local-infra -n "$NAMESPACE" 2>/dev/null && ok "Uninstalled local-infra" || warn "local-infra not installed"
kubectl delete namespace "$NAMESPACE" --ignore-not-found && ok "Deleted namespace $NAMESPACE"

echo ""
echo -e "${GREEN}Teardown complete.${NC}"
echo ""
echo "To also remove the nginx ingress controller:"
echo "  helm uninstall ingress-nginx -n ingress-nginx"
echo "  kubectl delete namespace ingress-nginx"

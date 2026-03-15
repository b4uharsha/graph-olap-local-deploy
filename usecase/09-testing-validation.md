# Testing and Validation Procedures

This guide covers comprehensive testing procedures for validating the Graph OLAP deployment on GKE.

## 1. Pre-Deployment Checklist

### Service Accounts

```bash
# Verify service accounts exist
gcloud iam service-accounts list --project=$PROJECT_ID | grep -E "(control-plane|wrapper|export-worker)-sa"

# Verify Workload Identity bindings
gcloud iam service-accounts get-iam-policy \
    control-plane-sa@${PROJECT_ID}.iam.gserviceaccount.com \
    --format=json | jq '.bindings[] | select(.role == "roles/iam.workloadIdentityUser")'
```

### GKE Cluster

```bash
# Verify cluster is running
gcloud container clusters describe $CLUSTER_NAME --region=$REGION --format="value(status)"

# Verify node pools
kubectl get nodes -o wide

# Verify Workload Identity is enabled
kubectl describe configmap -n kube-system | grep -A5 "workload-identity"
```

### Kubernetes Resources

```bash
# Verify namespace
kubectl get namespace graph-olap

# Verify service accounts with annotations
kubectl get serviceaccounts -n graph-olap -o yaml | grep "gcp-service-account"

# Verify RBAC
kubectl auth can-i create pods --as=system:serviceaccount:graph-olap:control-plane -n graph-olap

# Verify secrets exist (names only)
kubectl get secrets -n graph-olap

# Verify configmaps
kubectl get configmaps -n graph-olap
```

## 2. Component Health Checks

### Control Plane

```bash
# Check deployment status
kubectl get deployment control-plane -n graph-olap

# Check pod status
kubectl get pods -n graph-olap -l app=control-plane -o wide

# Check logs for startup errors
kubectl logs -n graph-olap -l app=control-plane -c control-plane --tail=50

# Check Cloud SQL Proxy logs
kubectl logs -n graph-olap -l app=control-plane -c cloud-sql-proxy --tail=50

# Test health endpoint
kubectl run test-health --rm -it --image=curlimages/curl --restart=Never -- \
    curl -s http://control-plane.graph-olap.svc.cluster.local:8080/health

# Test ready endpoint
kubectl run test-ready --rm -it --image=curlimages/curl --restart=Never -- \
    curl -s http://control-plane.graph-olap.svc.cluster.local:8080/ready
```

### Database Connectivity

```bash
# Exec into control-plane pod and test database
kubectl exec -n graph-olap -it deployment/control-plane -c control-plane -- \
    python -c "from control_plane.infrastructure.database import engine; print(engine.execute('SELECT 1').fetchone())"

# Check migrations ran
kubectl logs -n graph-olap -l app=control-plane -c control-plane | grep -i migration
```

### Export Worker

```bash
# Check deployment
kubectl get deployment export-worker -n graph-olap

# Check logs
kubectl logs -n graph-olap -l app=export-worker --tail=50
```

## 3. Functional Tests

### API Endpoints

```bash
# Create a test script
cat << 'EOF' > /tmp/test-api.sh
#!/bin/bash
set -e

API_URL="http://control-plane.graph-olap.svc.cluster.local:8080"
EMAIL="test@example.com"
ROLE="analyst"

echo "=== Testing Health ==="
curl -sf "$API_URL/health" | jq .

echo -e "\n=== Testing API Info ==="
curl -sf "$API_URL/api/" | jq .

echo -e "\n=== Testing List Mappings ==="
curl -sf "$API_URL/api/mappings" \
    -H "X-Username: $EMAIL" \
    -H "X-User-Role: $ROLE" | jq .

echo -e "\n=== Testing List Snapshots ==="
curl -sf "$API_URL/api/snapshots" \
    -H "X-Username: $EMAIL" \
    -H "X-User-Role: $ROLE" | jq .

echo -e "\n=== Testing List Instances ==="
curl -sf "$API_URL/api/instances" \
    -H "X-Username: $EMAIL" \
    -H "X-User-Role: $ROLE" | jq .

echo -e "\n=== All tests passed! ==="
EOF

# Run test script in cluster
kubectl run test-api --rm -it --image=curlimages/curl --restart=Never -- \
    sh -c "$(cat /tmp/test-api.sh)"
```

### Instance Lifecycle Test

```bash
# Full lifecycle test script
cat << 'EOF' > /tmp/test-lifecycle.sh
#!/bin/bash
set -e

API_URL="http://control-plane.graph-olap.svc.cluster.local:8080"
EMAIL="test@example.com"
ROLE="analyst"

echo "=== Creating Instance ==="
INSTANCE_RESPONSE=$(curl -sf -X POST "$API_URL/api/instances" \
    -H "Content-Type: application/json" \
    -H "X-Username: $EMAIL" \
    -H "X-User-Role: $ROLE" \
    -d '{
        "snapshot_id": 1,
        "wrapper_type": "ryugraph"
    }')
echo "$INSTANCE_RESPONSE" | jq .

INSTANCE_ID=$(echo "$INSTANCE_RESPONSE" | jq -r '.id')
echo "Created instance: $INSTANCE_ID"

echo -e "\n=== Waiting for instance to be ready ==="
for i in {1..60}; do
    STATUS=$(curl -sf "$API_URL/api/instances/$INSTANCE_ID" \
        -H "X-Username: $EMAIL" \
        -H "X-User-Role: $ROLE" | jq -r '.status')
    echo "Status: $STATUS"
    if [ "$STATUS" == "running" ]; then
        echo "Instance is running!"
        break
    fi
    sleep 5
done

echo -e "\n=== Getting Instance Details ==="
INSTANCE=$(curl -sf "$API_URL/api/instances/$INSTANCE_ID" \
    -H "X-Username: $EMAIL" \
    -H "X-User-Role: $ROLE")
echo "$INSTANCE" | jq .

WRAPPER_URL=$(echo "$INSTANCE" | jq -r '.url')
echo "Wrapper URL: $WRAPPER_URL"

echo -e "\n=== Testing Query ==="
if [ "$WRAPPER_URL" != "null" ]; then
    curl -sf -X POST "$WRAPPER_URL/query" \
        -H "Content-Type: application/json" \
        -H "X-Username: $EMAIL" \
        -H "X-User-Role: $ROLE" \
        -d '{"query": "MATCH (n) RETURN count(n) as count"}' | jq .
fi

echo -e "\n=== Deleting Instance ==="
curl -sf -X DELETE "$API_URL/api/instances/$INSTANCE_ID" \
    -H "X-Username: $EMAIL" \
    -H "X-User-Role: $ROLE"
echo "Instance deleted"

echo -e "\n=== Lifecycle test complete! ==="
EOF

# Run lifecycle test
kubectl run test-lifecycle --rm -it --image=curlimages/curl --restart=Never -- \
    sh -c "$(cat /tmp/test-lifecycle.sh)"
```

## 4. Wrapper Pod Tests

### Verify Wrapper Creation

```bash
# Watch for wrapper pods
kubectl get pods -n graph-olap -l wrapper-type -w

# Check wrapper logs
kubectl logs -n graph-olap -l wrapper-type=ryugraph --tail=100

# Check wrapper service
kubectl get svc -n graph-olap | grep wrapper

# Test wrapper health directly
WRAPPER_POD=$(kubectl get pods -n graph-olap -l wrapper-type -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n graph-olap $WRAPPER_POD -- curl -s localhost:8000/health
```

### Wrapper Query Test

```bash
# Get wrapper URL
WRAPPER_SVC=$(kubectl get svc -n graph-olap -l wrapper-type -o jsonpath='{.items[0].metadata.name}')

# Test query
kubectl run test-query --rm -it --image=curlimages/curl --restart=Never -- \
    curl -sf -X POST "http://${WRAPPER_SVC}.graph-olap.svc.cluster.local:8000/query" \
    -H "Content-Type: application/json" \
    -H "X-Username: test@example.com" \
    -H "X-User-Role: analyst" \
    -d '{"query": "MATCH (n) RETURN n LIMIT 5"}'
```

## 5. Load Balancer Tests

### Internal Load Balancer

```bash
# Check ingress status
kubectl get ingress -n graph-olap

# Get internal IP
kubectl get ingress control-plane-ingress -n graph-olap -o jsonpath='{.status.loadBalancer.ingress[0].ip}'

# Test from a VM in the same VPC
# (Run from a VM, not kubectl)
curl -v http://graph-olap.internal.your-domain.com/health
```

### NEG Status

```bash
# Check NEG annotations on services
kubectl get svc -n graph-olap -o json | jq '.items[] | {name: .metadata.name, neg: .metadata.annotations["cloud.google.com/neg"]}'

# Verify NEGs in GCP
gcloud compute network-endpoint-groups list --project=$PROJECT_ID | grep graph-olap
```

## 6. Security Tests

### Workload Identity

```bash
# Verify GCS access via Workload Identity
kubectl run test-wi --rm -it \
    --image=google/cloud-sdk:slim \
    --serviceaccount=control-plane \
    --namespace=graph-olap \
    -- gsutil ls gs://your-bucket/

# Verify Cloud SQL access
kubectl run test-wi-sql --rm -it \
    --image=google/cloud-sdk:slim \
    --serviceaccount=control-plane \
    --namespace=graph-olap \
    -- gcloud sql connect graph-olap-db --user=postgres --quiet
```

### RBAC Verification

```bash
# Test that control-plane can create pods
kubectl auth can-i create pods \
    --as=system:serviceaccount:graph-olap:control-plane \
    -n graph-olap

# Test that control-plane can delete pods
kubectl auth can-i delete pods \
    --as=system:serviceaccount:graph-olap:control-plane \
    -n graph-olap

# Test that wrapper SA cannot create pods
kubectl auth can-i create pods \
    --as=system:serviceaccount:graph-olap:wrapper \
    -n graph-olap
# Expected: no
```

## 7. Performance Tests

### Basic Load Test

```bash
# Install hey load testing tool
kubectl run load-test --rm -it \
    --image=williamyeh/hey \
    --restart=Never \
    -- -n 1000 -c 10 \
    -H "X-Username: test@example.com" \
    -H "X-User-Role: analyst" \
    http://control-plane.graph-olap.svc.cluster.local:8080/api/instances
```

### Query Performance

```bash
# Time a query
time kubectl run query-perf --rm -it --image=curlimages/curl --restart=Never -- \
    curl -sf -X POST "http://wrapper-xxx.graph-olap.svc.cluster.local:8000/query" \
    -H "Content-Type: application/json" \
    -H "X-Username: test@example.com" \
    -H "X-User-Role: analyst" \
    -d '{"query": "MATCH (n)-[r]->(m) RETURN count(r)"}'
```

## 8. Monitoring Verification

### Logs

```bash
# Check structured logging
kubectl logs -n graph-olap -l app=control-plane -c control-plane | head -5 | jq .

# Check for errors
kubectl logs -n graph-olap -l app=control-plane -c control-plane | grep -i error

# Check wrapper startup logs
kubectl logs -n graph-olap -l wrapper-type --tail=100 | grep -E "(loaded|ready|error)"
```

### Metrics

```bash
# If Prometheus is configured
kubectl run metrics-test --rm -it --image=curlimages/curl --restart=Never -- \
    curl -s http://control-plane.graph-olap.svc.cluster.local:8080/metrics
```

## 9. Cleanup Test Resources

```bash
# Delete test pods
kubectl delete pods -n graph-olap -l run

# Delete test instances
curl -X DELETE "http://control-plane:8080/api/instances/cleanup" \
    -H "X-Username: admin@example.com" \
    -H "X-User-Role: admin"
```

## 10. Troubleshooting Commands

```bash
# Get all resources in namespace
kubectl get all -n graph-olap

# Describe failing pod
kubectl describe pod -n graph-olap <pod-name>

# Get events
kubectl get events -n graph-olap --sort-by='.lastTimestamp'

# Check resource usage
kubectl top pods -n graph-olap

# Check node resources
kubectl top nodes

# Debug networking
kubectl run debug --rm -it --image=nicolaka/netshoot --restart=Never -- /bin/bash
```

## Validation Summary Checklist

```
[ ] Service accounts created with correct IAM roles
[ ] Workload Identity bindings configured
[ ] GKE cluster running with correct node pools
[ ] Kubernetes namespace, RBAC, secrets configured
[ ] Control Plane deployment healthy
[ ] Cloud SQL Proxy connecting successfully
[ ] Database migrations completed
[ ] Export Worker running
[ ] Internal Load Balancer provisioned
[ ] NEGs created for services
[ ] Health endpoints responding
[ ] API endpoints authenticated
[ ] Instance creation works
[ ] Wrapper pods spawn correctly
[ ] Wrapper queries execute
[ ] Instance deletion cleans up resources
[ ] Logs are structured JSON
[ ] No errors in any component logs
```

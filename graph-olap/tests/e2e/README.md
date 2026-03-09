# E2E Tests

End-to-end tests for the Graph OLAP platform. Tests run as Jupyter notebooks executed via Papermill, with a pytest harness for parallelism and cleanup.

## Quick Start (Local / OrbStack)

### Prerequisites

- **OrbStack** with Kubernetes enabled (`brew install orbstack`)
- **graph-olap-local-deploy** repo cloned as a sibling directory
- Platform deployed: `cd ../graph-olap-local-deploy && ./scripts/deploy.sh`

### Run Tests Locally

```bash
# From tests/e2e/
./scripts/run-tests.sh --cluster=orbstack
```

### Run a Single Notebook

```bash
./scripts/run-tests.sh --cluster=orbstack --notebook=04_cypher_basics
```

## Architecture

Tests connect to the platform via the nginx ingress controller (no port-forwarding needed):

```
pytest (local or in-cluster)
  ↓
http://localhost:30081  (or http://control-plane:8080 in-cluster)
  ↓
Nginx Ingress
  ↓
/api/*               → control-plane:8080
/wrapper/{slug}/*    → wrapper-{slug}:8000  (created dynamically per test)
```

## In-Cluster Execution (CI/CD)

Tests can run as a Kubernetes Job inside the cluster:

```bash
# 1. Build the test image (from graph-olap-local-deploy/)
SVC=e2e-tests ./scripts/build.sh

# 2. Deploy as a K8s Job
kubectl apply -f tests/e2e/k8s/e2e-test-job.yaml -n graph-olap-local

# 3. Follow logs
kubectl logs -f job/e2e-tests -n graph-olap-local

# 4. Re-run (delete old job first)
kubectl delete job e2e-tests -n graph-olap-local
kubectl apply -f tests/e2e/k8s/e2e-test-job.yaml -n graph-olap-local
```

The test image (`e2e-tests:latest`) is built by `local-deploy/docker/e2e-tests.Dockerfile`.

## Test Notebooks

19 platform test notebooks covering the full SDK surface:

| # | Notebook | Purpose |
| --- | -------- | ------- |
| 01 | `01_prerequisites` | Environment and connectivity checks |
| 02 | `02_health_checks` | Service health endpoints |
| 03 | `03_managing_resources` | CRUD: mappings, snapshots, instances |
| 04 | `04_cypher_basics` | Cypher query execution |
| 05 | `05_exploring_schemas` | Schema introspection |
| 06 | `06_graph_algorithms` | Native graph algorithms |
| 07 | `07_end_to_end_workflows` | Full export → query pipeline |
| 08 | `08_quick_start` | Minimal happy-path smoke test |
| 09 | `09_handling_errors` | Error handling and edge cases |
| 10 | `10_bookmarks` | Graph bookmarks |
| 11 | `11_instance_lifecycle` | Instance start/stop/delete |
| 12 | `12_export_data` | Starburst → GCS export pipeline |
| 13 | `13_advanced_mappings` | Complex field mappings |
| 14 | `14_version_diffing` | Snapshot version comparison |
| 15 | `15_background_jobs` | Async job management |
| 16 | `16_falkordb` | FalkorDB-specific features |
| 17 | `17_authorization` | Role-based access control |
| 18 | `18_admin_operations` | Admin/ops endpoints |
| 19 | `19_ops_configuration` | Platform configuration |

## Cleanup

Tests use a cleanup framework so resources are deleted even on failure.

Check for leaked resources:

```bash
python scripts/check_test_resources.py \
  --api-url http://localhost:30081 \
  --username e2e-test-user

# Force cleanup
python scripts/check_test_resources.py --cleanup --force
```

## Module Structure

```
tests/e2e/
├── clusters/
│   └── orbstack.env              # Cluster config (URL, context, namespace)
├── notebooks/platform-tests/     # 19 Jupyter test notebooks
├── scripts/
│   ├── run-tests.sh              # Main entry point
│   ├── exec-job.sh               # K8s Job execution
│   ├── exec-jupyter.sh           # Jupyter execution
│   ├── cleanup_before_tests.py   # Pre-flight API cleanup
│   └── check_test_resources.py   # Orphan detection
├── tests/
│   ├── conftest.py               # Pytest fixtures
│   ├── test_notebook_execution.py # Papermill runner
│   ├── test_create_from_mapping.py
│   └── test_schema_metadata.py
├── utils/
│   ├── cleanup.py                # Cleanup context manager
│   └── constants.py
├── k8s/
│   └── e2e-test-job.yaml         # K8s Job spec (uses e2e-tests:latest image)
├── entrypoint.sh                 # Container entrypoint
├── pyproject.toml                # Dependencies
└── README.md
```

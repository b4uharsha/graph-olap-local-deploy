# Graph OLAP — Local Deployment

Self-contained tooling to build and run the full Graph OLAP stack on any developer machine. No internal tools, no private registries, no Earthly.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| kubectl | any | https://kubernetes.io/docs/tasks/tools/ |
| Helm | 3+ | `brew install helm` |
| Local Kubernetes | any | see below |

**Local Kubernetes options (pick one):**
- **OrbStack** (macOS, recommended): `brew install orbstack` → enable K8s in settings
- **Rancher Desktop** (macOS/Windows/Linux): https://rancherdesktop.io
- **Docker Desktop**: enable Kubernetes in preferences
- **minikube**: `brew install minikube && minikube start`
- **kind**: `brew install kind && kind create cluster`

**Source code** — this folder must be a sibling of the `graph-olap` monorepo:
```
parent-dir/
├── graph-olap/                  ← source code (monorepo)
└── graph-olap-local-deploy/     ← this folder
```

If your layout differs, set `MONOREPO_ROOT`:
```bash
export MONOREPO_ROOT=/path/to/graph-olap
```

## Quick Start

```bash
# 1. Check prerequisites
make prereqs

# 2. Build all Docker images (~10-20 min first time, uses public base images)
make build

# 3. Deploy to local Kubernetes
make deploy

# 4. Verify
make status
curl http://localhost:30081/health
```

The API is available at **http://localhost:30081** once deployment completes.

## What Gets Deployed

| Component | Image | Description |
|-----------|-------|-------------|
| PostgreSQL | `postgres:15-alpine` (public) | Control-plane database |
| Extension Server | `ghcr.io/predictable-labs/extension-repo` (public) | Graph algorithm extensions |
| Control Plane | `control-plane:latest` (local build) | FastAPI REST API |
| Export Worker | `export-worker:latest` (local build) | Background export job processor |
| OAuth2 Proxy | `quay.io/oauth2-proxy/oauth2-proxy` (public) | JWT validation at the ingress |
| nginx Ingress | installed via Helm (public) | Routes traffic into the cluster |

**Wrapper images** (`ryugraph-wrapper`, `falkordb-wrapper`) are built locally and stored in Docker. The control-plane spawns wrapper pods dynamically when graph instances are created — they are not pre-deployed.

## Optional: Starburst Galaxy

Export jobs query data via Starburst Galaxy. Without credentials the API starts normally but export job execution will fail:

```bash
export STARBURST_USER=your-service-account@yourorg
export STARBURST_PASSWORD=your-password
make deploy
```

Create a service account in Galaxy UI: **Settings → Service Accounts → Create**.

## Optional: Google Cloud Storage

Snapshot operations read/write parquet files from GCS. Without a service account key a placeholder empty secret is created automatically (the pods start, but GCS operations fail).

To enable real GCS access, set `GCP_SA_KEY_JSON` before deploying:
```bash
export GCP_SA_KEY_JSON=$(cat /path/to/sa-key.json)
make deploy
```

`deploy.sh` detects `GCP_SA_KEY_JSON` automatically and creates the secret.
You can also update an existing deployment:
```bash
kubectl create secret generic gcp-sa-key \
  --from-file=key.json=/path/to/sa-key.json \
  -n graph-olap-local \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl rollout restart deployment/graph-olap-export-worker -n graph-olap-local
```

> **Note:** The fake-gcs-server (`fsouza/fake-gcs-server`) is deployed automatically for development but only the export-worker uses it. Wrapper pods (FalkorDB/Ryugraph) require real GCS to load Parquet data.

## Demo Notebook

A working end-to-end demo notebook is included at `notebooks/graph-olap-demo.ipynb`. It is automatically copied into the Jupyter pod during `make deploy`.

Open it at: **[http://localhost:30081/jupyter/lab/tree/graph-olap-demo.ipynb](http://localhost:30081/jupyter/lab/tree/graph-olap-demo.ipynb)**

The notebook covers:

1. Create a mapping (Customer / Nation / SalesOrder from TPC-H)
2. Create an instance + patch the starburst catalog (see Known Issues)
3. Poll export progress
4. Run Cypher queries
5. Visualise the graph with PyVis

> Requires `STARBURST_USER`, `STARBURST_PASSWORD`, and `GCP_SA_KEY_JSON` to be set.

## Known Issues

### `starburst_catalog` hardcoded as `bigquery`

The control-plane creates export jobs with `starburst_catalog = 'bigquery'` regardless of configuration. This means all export jobs fail silently — the export-worker picks them up but cannot find any tables.

**Workaround (already in the demo notebook):** Immediately after creating an instance, patch the database:

```python
import psycopg2
conn = psycopg2.connect(host="postgres", port=5432, dbname="control_plane",
                        user="control_plane", password="control_plane")
conn.autocommit = True
with conn.cursor() as cur:
    cur.execute(
        "UPDATE export_jobs SET starburst_catalog = 'tpch' WHERE snapshot_id = %s AND starburst_catalog = 'bigquery'",
        (snapshot_id,)
    )
conn.close()
```

**Root cause:** `SnapshotService` in `packages/control-plane` does not read `starburst_catalog` from settings when creating export jobs. Requires a fix in the monorepo source.

## Common Commands

```bash
make build                      # Build all images
make build SVC=control-plane    # Build one image

make deploy                     # Deploy / re-deploy full stack
make status                     # Show pod and service health
make logs SVC=control-plane     # Tail logs
make logs SVC=export-worker

make teardown                   # Delete everything (namespace)
```

## Rebuilding After Code Changes

```bash
make build SVC=control-plane    # Rebuild one service
make deploy                     # Re-deploy (Helm detects the new image)
```

## Troubleshooting

**Pods in CrashLoopBackOff:**
```bash
make logs SVC=control-plane
kubectl describe pod -n graph-olap-local -l app=graph-olap-control-plane
```

**Image not found (ErrImageNeverPull):**
```bash
make build          # Images were not built or need rebuilding
```

**Helm dependency errors:**
```bash
# Manually update helm dependencies
helm dependency update helm/charts/graph-olap
helm dependency update helm/charts/local-infra
```

**Port 30081 not responding after deploy:**
- Services may still be starting — wait 60 seconds and retry
- Check `make status` for pod readiness
- OrbStack/Rancher Desktop expose NodePorts on `localhost` directly
- Docker Desktop: same
- minikube: run `minikube service -n graph-olap-local graph-olap-control-plane --url`

**Reset everything:**
```bash
make teardown
make deploy
```

## Directory Structure

```
local-deploy/
├── Makefile                   # Entry point: make build / deploy / status
├── .env.example               # Environment variable template
├── docker/
│   ├── control-plane.Dockerfile     # Uses public Chainguard Python image
│   ├── export-worker.Dockerfile
│   ├── falkordb-wrapper.Dockerfile
│   └── ryugraph-wrapper.Dockerfile
├── helm/
│   ├── values-local.yaml      # Helm values for the local stack
│   └── charts/                # Helm charts (graph-olap, local-infra, jupyter-labs, common)
├── k8s/
│   ├── control-plane-ingress.yaml   # nginx ingress routes
│   ├── control-plane-rbac.yaml      # RBAC for dynamic wrapper pod spawning
│   └── fake-gcs-server.yaml         # Local GCS emulator (export-worker only)
├── notebooks/
│   └── graph-olap-demo.ipynb  # End-to-end demo (auto-copied to Jupyter pod)
└── scripts/
    ├── prereqs.sh             # Prerequisite checker
    ├── build.sh               # Docker build orchestration
    ├── deploy.sh              # Helm deploy orchestration
    └── teardown.sh            # Cleanup
```

## Image Build Notes

- All images use **public base images** — no internal registry needed
- `control-plane`, `falkordb-wrapper`, `ryugraph-wrapper`: Chainguard Python (`cgr.dev/chainguard/python`)
- `export-worker`: Chainguard Python
- `ryugraph-wrapper`: `python:3.12-slim` (ryugraph requires Python 3.12)
- Builds run from the **monorepo root** as Docker context so all `packages/` are available
- On minikube/kind, the build script automatically loads images into the cluster

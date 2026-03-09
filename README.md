# Graph OLAP

Self-service graph analytics platform — run warehouse data as in-memory graphs.

## Repository Layout

| Folder | What it is |
|---|---|
| [`graph-olap/`](graph-olap/) | Service source code — control-plane, export-worker, FalkorDB wrapper, KuzuDB wrapper, Python SDK |
| [`graph-olap-local-deploy/`](graph-olap-local-deploy/) | Local deployment — Helm charts, Kubernetes manifests, scripts, demo notebooks, docs |

## Quick Start

See [`graph-olap-local-deploy/README.md`](graph-olap-local-deploy/README.md) for full setup instructions.

```bash
cd graph-olap-local-deploy
make build
make deploy
```

Opens at `http://localhost:30081/jupyter/lab` with 6 demo notebooks pre-loaded.

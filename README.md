# Graph OLAP

**Self-service graph analytics on your warehouse data — run as isolated in-memory graphs, query in milliseconds.**

---

## The Problem

Analysts need to explore connected data — fraud rings, supply chains, customer networks, recommendation graphs. Running these as SQL joins is painful:

- Multi-hop traversal queries that should take **milliseconds** take **minutes** in SQL
- Every analyst sharing the same warehouse means resource contention
- Graph databases exist, but loading warehouse data into them is a manual, fragile process

## The Solution

Graph OLAP is a platform that automates the full pipeline from warehouse to queryable graph:

1. **Define once** — describe which warehouse tables become nodes and edges (a *Mapping*)
2. **Spawn on demand** — create a graph *Instance* from that mapping; the platform exports data to Parquet and loads it into a dedicated in-memory graph pod
3. **Query instantly** — run Cypher traversal queries directly against your pod; results in milliseconds, no warehouse touched
4. **Auto-expires** — pods live for a configured TTL then disappear; Parquet is preserved so you can recreate instantly

Each analyst gets a **completely isolated pod** — no shared state, no contention.

---

## Architecture

```text
http://localhost:30081
        │
        ▼
nginx Ingress (NodePort 30081)
        │
        ├── /api/*      →  Control Plane (FastAPI)   ─── PostgreSQL
        ├── /jupyter    →  Jupyter Labs               ─── 6 demo notebooks
        └── /health     →  Health check

Control Plane ──────────────────────────────────────────────────────────
  Manages mappings, snapshots, instances, users
  Calls Kubernetes API to spawn / delete wrapper pods
  Reconciliation loop every ~30s — promotes ready snapshots to running pods

Export Worker ───────────────────────────────────────────────────────────
  Polls for export jobs → runs UNLOAD queries on Starburst Galaxy
  Writes Parquet files to GCS (or fake-gcs-local in local mode)

Wrapper Pod (one per analyst instance) ──────────────────────────────────
  FalkorDB (Redis-based) or KuzuDB (columnar) — chosen per instance
  Downloads Parquet from GCS on startup, loads graph at ~200k rows/sec
  Accepts Cypher queries directly — fully in-memory, sub-millisecond
```

### End-to-End Flow

```text
Analyst
  │
  ├─ POST /api/mappings          Define nodes + edges from SQL
  │         │
  │         └─► PostgreSQL       Mapping stored
  │
  ├─ POST /api/instances         Trigger export pipeline
  │         │
  │         └─► Export Worker ──► Starburst UNLOAD ──► Parquet in GCS
  │                                                         │
  │                                    Reconciler (~30s) ◄──┘
  │                                         │
  │                                    K8s spawns Wrapper Pod
  │                                         │
  │                                    Pod loads graph (~200k rows/sec)
  │                                         │
  └─ Cypher query ──────────────────────────►  Result in milliseconds ⚡
```

### Services

| Service | Role | Image |
|---|---|---|
| **Control Plane** | REST API — orchestrates everything via K8s API | `control-plane:latest` |
| **Export Worker** | Runs Starburst UNLOAD jobs, writes Parquet to GCS | `export-worker:latest` |
| **FalkorDB Wrapper** | In-memory graph pod (Redis-based) — fast lookups | `falkordb-wrapper:local` |
| **Ryugraph Wrapper** | In-memory graph pod (KuzuDB) — large scans + algorithms | `ryugraph-wrapper:local` |
| **Jupyter Labs** | Notebook environment with SDK + 6 demo notebooks | `jupyter-labs:latest` |
| **PostgreSQL** | Control plane database | `postgres:15-alpine` |
| **Extension Server** | Graph algorithm extensions (PageRank, BFS, Louvain) | `extension-server` |
| **Fake GCS Server** | Local GCS emulator — no real GCP account needed | `fake-gcs-server` |

---

## Tested & Validated

### All pods running

![All pods running](graph-olap-local-deploy/docs-local/docs/assets/screenshots/pods-running.png)

### Movie graph — PyVis interactive visualisation (notebook 01)

Actors, directors, movies — loaded from synthetic Parquet, queried via Cypher, rendered with PyVis. Traversal query returned in **1ms**.

![Movie graph PyVis](graph-olap-local-deploy/docs-local/docs/assets/screenshots/movie-graph.png)

### IPL T20 cricket graph — player/team/venue network (notebook 04)

Players, teams, matches, seasons — full graph analytics on cricket stats data.

![IPL T20 graph](graph-olap-local-deploy/docs-local/docs/assets/screenshots/ipl-graph.png)

### End-to-end test results

```text
✓ Mapping created               mapping_id=19
✓ Instance created              instance_id=19, snapshot_id=19
✓ Parquet uploaded to fake-gcs  e2e@test.com/19/v1/19/nodes/Movie/
✓ Snapshot marked ready         UPDATE snapshots SET status='ready'
✓ Wrapper pod reached Running   ~25 seconds
✓ Cypher query returned         3 actors, 3 movies, ACTED_IN traversal — 1ms
✓ Cleanup complete
```

---

## Demo Notebooks

Six notebooks are pre-loaded in Jupyter Labs — no credentials needed, all generate synthetic data:

| # | Notebook | What it demonstrates |
|---|---|---|
| `00` | `00-cleanup.ipynb` | List and bulk-delete instances |
| `01` | `01-movie-graph-demo.ipynb` | Actor/director/movie graph — Cypher queries, PyVis |
| `02` | `02-music-graph-demo.ipynb` | Artist/album/track graph — multi-hop traversals |
| `03` | `03-ecommerce-graph-demo.ipynb` | Product/customer/order — recommendation queries |
| `04` | `04-ipl-t20-graph-demo.ipynb` | Cricket stats — player/team/match relationships |
| `05` | `05-algorithms-demo.ipynb` | Co-actor network — PageRank, Betweenness, Louvain, PyVis |

---

## Quick Start

```bash
cd graph-olap-local-deploy

# Optional — configure real Starburst + GCS credentials
# (skip to run demo notebooks with synthetic data only)
make secrets

# Build all Docker images (~10 min first time)
make build

# Deploy to local Kubernetes
make deploy
```

| Endpoint | What it is |
|---|---|
| `http://localhost:30081/jupyter/lab` | Jupyter Labs — 6 demo notebooks |
| `http://localhost:30081/api/...` | Control Plane REST API |
| `http://localhost:30081/health` | Health check |
| `http://localhost:30082` | Full documentation site |

Full setup instructions: [`graph-olap-local-deploy/README.md`](graph-olap-local-deploy/README.md)

---

## Repository Layout

| Folder | What it is |
|---|---|
| [`graph-olap/`](graph-olap/) | Service source code — control-plane, export-worker, FalkorDB wrapper, KuzuDB wrapper, Python SDK |
| [`graph-olap-local-deploy/`](graph-olap-local-deploy/) | Local deployment — Helm charts, Kubernetes manifests, scripts, demo notebooks, docs |

---

## Use Cases

- **Fraud detection** — traverse transaction networks to find rings and mules
- **AML / financial crime** — multi-hop relationship queries across accounts and entities
- **Supply chain** — map supplier dependencies, find single points of failure
- **Customer 360** — connect customers, orders, products, and segments in one graph
- **Recommendation** — co-purchase / co-actor graphs with community detection

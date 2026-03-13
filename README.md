# Graph OLAP Platform

> **Turn your data warehouse into a queryable graph in seconds. Sub-millisecond traversals. Fully isolated per analyst. Runs on your laptop — deploys to production with the same charts.**

---

## What is this?

**Graph OLAP** is an open, self-service platform that bridges two worlds that have never talked to each other properly:

- Your **data warehouse** (Starburst, BigQuery, Snowflake, Databricks) — where all your data lives
- A **graph database** — where relationship questions become trivial

Today, if you want to ask "which accounts are connected to this fraud suspect through 4 hops of transactions?", you either write 6 nested SQL joins that take 4 minutes — or you hire a graph database team, build an ETL pipeline, and wait weeks.

**Graph OLAP removes that entire problem.** An analyst defines which SQL tables become nodes and edges. The platform exports the data, loads it into an in-memory graph, and returns Cypher query results in milliseconds. No DBA. No ETL pipeline. No shared cluster.

---

## Why does this matter?

SQL was designed for rows. Graphs were designed for connections. Some questions are fundamentally about relationships — and SQL was never meant to answer them.

```sql
-- Find accounts 4 hops away in SQL — already painful, runtime ~4 min on 10M rows
SELECT a1.id, a2.id, a3.id, a4.id
FROM accounts a1
JOIN transactions t1 ON t1.from_account = a1.id
JOIN accounts a2 ON t1.to_account = a2.id
JOIN transactions t2 ON t2.from_account = a2.id
JOIN accounts a3 ON t2.to_account = a3.id
JOIN transactions t3 ON t3.from_account = a3.id
JOIN accounts a4 ON t3.to_account = a4.id
WHERE a1.id = 12345
```

```cypher
-- The same question in Cypher — runtime ~2ms
MATCH (a:Account {id: 12345})-[:TRANSFERRED*1..4]->(suspect:Account)
RETURN suspect
```

The gap is not compute power. It is the wrong data structure.

---

## The Industry Gap

| What analysts need | What exists today | The problem |
| -- | -- | -- |
| Self-service graph on warehouse data | Neo4j, TigerGraph, Neptune | Requires dedicated ETL, engineering team, always-on cost |
| Fresh data from the warehouse | Batch import / CDC pipelines | Hours or days of lag |
| Per-analyst isolation | Shared clusters | One heavy query degrades everyone |
| Zero idle cost | Always-on database | Paying for compute even when no one is querying |
| Local development story | Cloud-only graph databases | Cannot run locally without a full cluster |

**Nobody has built an ephemeral, per-analyst, self-service, warehouse-native graph layer — until now.**

---

## How It Works

```text
Analyst defines a Mapping
  → which SQL tables become nodes
  → which SQL tables become edges
        │
        ▼
Analyst creates an Instance ("give me this as a live graph")
        │
        ▼
Export Worker runs SELECT on Starburst/BigQuery
  → writes columnar Parquet files to GCS
        │
        ▼
Control Plane detects snapshot ready
  → Kubernetes spawns a dedicated Wrapper Pod (FalkorDB or RyuGraph)
        │
        ▼
Wrapper Pod downloads Parquet → loads graph into memory (~200k rows/sec)
        │
        ▼
Analyst queries via Cypher → result in milliseconds ⚡
        │
        ▼
TTL expires → pod deleted → Parquet stays in GCS → recreate anytime
```

Each analyst gets a **completely isolated pod**. No shared state. No interference. When you are done, the pod is deleted automatically. The Parquet snapshot stays in GCS — recreate the graph instantly anytime.

---

## Real-World Use Cases

### Fraud Detection — Banking

> *"Show me every account within 3 hops of this suspicious account, connected through transactions over $10,000 in the last 30 days."*

In SQL: 6 self-joins, multiple CTEs, minutes on a large dataset.
In Graph OLAP: one Cypher query, 3ms.

### Anti-Money Laundering (AML)

> *"Find circular money flows — money that leaves account A and returns to account A within 5 hops."*

Classic cycle detection. Impossible in SQL without recursive CTEs that time out at scale. Natural in a graph traversal.

### Supply Chain Risk

> *"Which of our tier-1 suppliers depend on the same tier-3 component manufacturer? If that factory goes down, what products are affected?"*

Map the entire dependency graph. Run shortest-path. Identify single points of failure in seconds.

### Customer 360 / Recommendation

> *"Customers who bought the same products as this customer, but from different regions — who are they and what else did they buy?"*

Multi-hop co-purchase traversal. SQL requires multiple joins across large tables. Graph returns it in one pattern match.

### Knowledge Graphs / Access Control / HR

> *"Who in the organisation has access to system X, through what role chain, and who approved each step?"*

Access control chains, org hierarchies, IT dependency graphs — all relationship problems that graphs solve naturally.

---

## What Makes This Different

| | Traditional Graph DB | **Graph OLAP** |
| -- | -- | -- |
| Data loading | Manual ETL pipeline, custom maintenance | Define a SQL query — done |
| Isolation | Shared cluster | Each analyst gets a dedicated pod |
| Startup time | Hours (provision + load) | ~10 seconds from definition to query |
| Cost when idle | Full database running 24/7 | Pod deleted after TTL — zero idle cost |
| Self-service | Requires DBA / engineering | Analyst does it from a notebook cell |
| Local development | Cloud-only or complex setup | Full stack runs on a laptop — `make deploy` |
| Data freshness | Stale (batch / CDC lag) | Point-in-time export from warehouse on demand |

---

## Validated — Running on a MacBook Pro

The full platform has been verified end-to-end on a local laptop. All pods running, all notebooks passing, Cypher queries returning results in under 2ms:

```text
✓ All pods running         control-plane, export-worker, falkordb-wrapper,
                           ryugraph-wrapper, jupyter-labs, postgres,
                           extension-server, fake-gcs-local

✓ Mapping created          mapping_id=19
✓ Instance created         instance_id=19, snapshot_id=19
✓ Parquet uploaded         e2e@test.com/19/v1/19/nodes/Movie/part-0.parquet
✓ Wrapper pod running      ~25 seconds from instance creation
✓ Cypher query returned    3 actors, 3 movies, ACTED_IN traversal — 1ms
✓ Graph algorithms         PageRank, Betweenness, Louvain, Shortest Path — all passing
✓ Cleanup complete         pod deleted, mapping and instance removed
```

### 6 Demo Notebooks — all verified

| # | Notebook | What it shows |
| -- | -- | -- |
| `01` | Movie Graph | Actor / director / movie network — Cypher traversals, PyVis interactive graph |
| `02` | Music Graph | Artist / album / track — multi-hop genre traversals |
| `03` | E-commerce Graph | Product / customer / order — recommendation queries |
| `04` | IPL T20 Graph | Cricket players / teams / matches / seasons — full sports graph analytics |
| `05` | Algorithms Demo | Co-actor network — PageRank, Betweenness Centrality, Louvain community detection, Shortest Path |
| `00` | Cleanup | Bulk instance management utility |

All notebooks run without any cloud credentials — they use a local GCS emulator and synthetic data.

---

## Also Deployed to Production

Beyond the local laptop demo, the platform is running in production on **Google Kubernetes Engine (GKE)** — real data, real users, real infrastructure:

- All services deployed and running in a dedicated GKE cluster
- CI/CD pipeline fully automated — 5 images built and deployed end-to-end
- Starburst Enterprise connected — real HSBC WPB GLH data
- KEDA auto-scaling — export-worker scales to zero when idle, scales up on demand
- Workload Identity — no service account keys anywhere, GCS accessed natively
- Cloud SQL Auth Proxy — secure database connectivity
- CoreDNS — each wrapper instance gets a stable in-cluster URL automatically on spawn
- FalkorDB and RyuGraph both deployed — analyst chooses engine per instance

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                 localhost:30081 (nginx ingress)                  │
│                                                                  │
│   /api/*    ──►  Control Plane (FastAPI + Python)                │
│   /jupyter  ──►  Jupyter Labs                                    │
│   /health   ──►  Health check                                    │
└──────────────────────┬──────────────────────────────────────────┘
                       │
          ┌────────────▼─────────────┐
          │      Control Plane        │  FastAPI · Python
          │  - REST API               │  Manages: mappings, snapshots,
          │  - Kubernetes API client  │  instances, users
          │  - Reconciliation loop    │  Spawns / deletes wrapper pods
          └──────┬──────────┬────────┘
                 │          │
    ┌────────────▼──┐  ┌────▼──────────────────┐
    │  PostgreSQL   │  │    Export Worker        │  Python
    │  (metadata)   │  │  Polls export jobs      │
    │  mappings     │  │  → Starburst SELECT     │
    │  snapshots    │  │  → Parquet via PyArrow  │
    │  instances    │  │  → Upload to GCS        │
    └───────────────┘  └────────────────────────┘
                                  │
                                  │ Parquet files
                        ┌─────────▼──────────┐
                        │  GCS / fake-gcs     │  Cloud Storage
                        │  (Parquet store)    │  or local emulator
                        └─────────┬──────────┘
                                  │ Download on startup
          ┌───────────────────────▼──────────────────────┐
          │        Wrapper Pod  (one per analyst)          │
          │                                               │
          │   ┌──────────────┐  or  ┌──────────────────┐  │
          │   │   FalkorDB   │      │  RyuGraph (Kuzu)  │  │
          │   │  In-memory   │      │  Columnar graph   │  │
          │   │  fast lookup │      │  algorithms+scan  │  │
          │   └──────────────┘      └──────────────────┘  │
          │                                               │
          │   Cypher query → result in milliseconds ⚡    │
          └───────────────────────────────────────────────┘
```

### Services — What Runs and What It Does

| Service | Role |
| -- | -- |
| **Control Plane** | The brain of the platform. FastAPI REST API that manages all mappings, snapshots, and instances. Talks to the Kubernetes API to spawn and delete wrapper pods on demand. Stores all state in PostgreSQL. |
| **Export Worker** | Background job processor. Polls the control-plane for pending export jobs, connects to Starburst or BigQuery, runs SELECT queries, converts results to Parquet via PyArrow, and uploads to GCS. Scales to zero when idle (KEDA). |
| **FalkorDB Wrapper** | Ephemeral graph pod using [FalkorDB](https://falkordb.com) — a Redis-based in-memory graph engine. Best for fast point lookups and short traversals. Spawned per instance, torn down after TTL. Serves Cypher queries over HTTP. |
| **RyuGraph Wrapper** | Ephemeral graph pod using [KuzuDB](https://kuzudb.com) — a columnar in-memory graph engine. Best for large graph scans, full-graph algorithms (PageRank, Louvain, BFS). Same API as FalkorDB wrapper. |
| **PostgreSQL** | Stores all platform metadata — mappings, snapshots, instances, users. |
| **Extension Server** | Provides graph algorithm extensions (PageRank, Betweenness Centrality, Louvain community detection, Shortest Path) to wrapper pods via HTTP. |
| **Jupyter Labs** | Pre-loaded notebook environment with the Graph OLAP Python SDK and 6 demo notebooks ready to run. |
| **Fake GCS** | Local GCS emulator for laptop dev — zero cloud account needed. Demo notebooks upload Parquet directly here. Swapped for real GCS when credentials are provided. |

### Technology Stack

| Layer | Technology | Why |
| -- | -- | -- |
| **API** | FastAPI (Python) | Async REST, lightweight, production-grade |
| **Graph engine A** | [FalkorDB](https://falkordb.com) | Redis-based in-memory graph. Fastest for point lookups and short traversals. OpenCypher. |
| **Graph engine B** | [RyuGraph / KuzuDB](https://kuzudb.com) | Columnar graph. Better for full graph scans, large datasets, and algorithm workloads (PageRank, BFS, Louvain). |
| **Data format** | Apache Parquet | Columnar, compressed, fast to load. Warehouse-native. |
| **Warehouse** | Starburst / BigQuery / any | SQL over any warehouse. Export via SELECT + PyArrow. |
| **Storage** | Google Cloud Storage | Durable Parquet store. `fake-gcs-local` emulates it locally. |
| **Orchestration** | Kubernetes | Spawns / deletes wrapper pods on demand. Works on any K8s cluster. |
| **Autoscaling** | KEDA | Export-worker scales to zero when idle. |
| **Packaging** | Helm | Same charts for local dev and production GKE. |
| **Notebooks** | Jupyter Labs | Pre-loaded with Python SDK and 6 demo notebooks. |
| **Algorithms** | NetworkX + Extension Server | PageRank, Betweenness Centrality, Louvain, BFS, Shortest Path. |

---

## Quick Start

```bash
# Prerequisites: Docker, kubectl, Helm, local Kubernetes (OrbStack / Rancher / Docker Desktop / minikube)

git clone <this-repo>
cd graph-olap-local-deploy

# Optional: configure real Starburst + GCS credentials
# Skip to run all 6 demo notebooks on synthetic data without any cloud account
make secrets

# Build all Docker images (~10–20 min first time)
make build

# Deploy to local Kubernetes
make deploy

# Open Jupyter Labs
open http://localhost:30081/jupyter/lab
```

| Endpoint | What it is |
| -- | -- |
| `http://localhost:30081/jupyter/lab` | Jupyter Labs — open and run any notebook |
| `http://localhost:30081/api/...` | Control Plane REST API |
| `http://localhost:30081/health` | Health check |
| `http://localhost:30082` | Full local documentation site |

---

## Local Kubernetes Options

| Tool | Platform | How to install |
| -- | -- | -- |
| **OrbStack** (recommended for macOS) | macOS | `brew install orbstack` → enable K8s in settings |
| **Rancher Desktop** | macOS / Windows / Linux | [rancherdesktop.io](https://rancherdesktop.io) |
| **Docker Desktop** | macOS / Windows | Enable Kubernetes in preferences |
| **minikube** | Any | `brew install minikube && minikube start` |
| **kind** | Any | `brew install kind && kind create cluster` |

---

## Common Commands

```bash
make build                      # Build all images
make build SVC=control-plane    # Build one image
make deploy                     # Deploy / re-deploy full stack
make status                     # Show pod and service health
make logs SVC=control-plane     # Tail logs
make secrets                    # Interactive credential setup
make teardown                   # Delete everything
```

---

## Repository Layout

```text
graph-olap-local-deploy/
├── Makefile                          # Entry point: make build / deploy / status / secrets
├── docker/                           # Dockerfiles for all services
├── helm/
│   ├── values-local.yaml             # Helm values (credentials injected by make secrets)
│   └── charts/                       # Helm charts (graph-olap, local-infra, jupyter-labs)
├── k8s/
│   ├── control-plane-ingress.yaml
│   ├── control-plane-rbac.yaml       # RBAC for dynamic wrapper pod spawning
│   └── fake-gcs-server.yaml
├── notebooks/
│   ├── graph_olap_sdk.py             # Python SDK used by all notebooks
│   ├── 01-movie-graph-demo.ipynb
│   ├── 02-music-graph-demo.ipynb
│   ├── 03-ecommerce-graph-demo.ipynb
│   ├── 04-ipl-t20-graph-demo.ipynb
│   └── 05-algorithms-demo.ipynb
├── scripts/                          # Build, deploy, teardown, secrets
└── docs-local/                       # Local documentation site (localhost:30082)
```

Source code lives in the sibling monorepo `graph-olap/`. This repo handles local deployment only.

```text
parent-dir/
├── graph-olap/                  ← service source code
└── graph-olap-local-deploy/     ← this repo (local deployment)
```

---

## The Bigger Picture

This platform proves that the **graph layer does not need to be a separate, always-on, shared database**. It can be:

- **Ephemeral** — spin up for a session, tear down when done
- **Per-analyst** — complete isolation, no shared state
- **Warehouse-native** — data flows from the warehouse on demand, always fresh
- **Self-service** — no DBA, no ticket, no ETL team
- **Cost-efficient** — zero idle cost, pay only for what you use

The graph database was never the bottleneck. The bottleneck was the missing layer between the warehouse and the graph. This platform is that layer.

---

## Documentation

Full documentation available at `http://localhost:30082` after deploy — covers architecture, API reference, SDK guide, notebook tutorials, and data loading.

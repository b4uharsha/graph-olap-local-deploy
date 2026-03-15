<div align="center">

# Graph OLAP Platform

### See the connections your spreadsheets are hiding.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Production Ready](https://img.shields.io/badge/status-Production%20Ready-success)](usecase/README.md)
[![Try It](https://img.shields.io/badge/demo-Run%20Locally-blue)](#quick-start)

</div>

---

## The Problem We Solve

**Your company has data. Lots of it.** Customer records, transactions, suppliers, employees, products — all sitting in databases and spreadsheets.

But here's the thing: **the most valuable insights are in the connections between data, not the data itself.**

- Which customers are connected to a fraud suspect through shared accounts?
- If this supplier fails, which products are affected through the supply chain?
- Who has access to sensitive systems, and through what chain of approvals?

**These questions are nearly impossible to answer with traditional tools.** You'd need weeks of engineering work, expensive consultants, and complex data pipelines.

**Graph OLAP answers them in seconds.**

---

## How It Works (The Simple Version)

Think of it like **Google Maps for your data.**

| Without Graph OLAP | With Graph OLAP |
|-------------------|-----------------|
| Like reading a list of every street name to find a route | Like seeing the map and finding the path instantly |
| "Find connections" = weeks of manual analysis | "Find connections" = type a question, get an answer |
| Requires a team of engineers | Any analyst can do it themselves |
| Expensive infrastructure running 24/7 | Spins up when you need it, shuts down when you're done |

---

## Real Examples (No Technical Jargon)

### "Who's connected to this fraud suspect?"

A bank analyst needs to find every account connected to a suspicious account through money transfers — up to 4 steps away.

- **The old way:** Write complex database queries, wait 4 minutes, probably miss something
- **With Graph OLAP:** Ask the question in plain English, get the complete network in 2 milliseconds

### "What happens if this factory shuts down?"

A supply chain manager needs to know which products depend on a single overseas manufacturer.

- **The old way:** Dig through spreadsheets for days, build manual dependency charts
- **With Graph OLAP:** See the entire supply chain visually, identify every affected product instantly

### "How did this employee get access to this system?"

An auditor needs to trace the approval chain for sensitive system access.

- **The old way:** Request reports from IT, wait weeks, piece together the story manually
- **With Graph OLAP:** See the complete approval chain in one view, instantly

### "Which patients are affected by this drug recall?"

A pharma safety officer needs to trace every patient who received a medication from a recalled batch — through hospitals, pharmacies, and distributors.

- **The old way:** Call each distributor, cross-reference spreadsheets, takes days or weeks
- **With Graph OLAP:** Trace the complete distribution chain instantly, identify every affected patient in seconds

---

## Why This Matters

| Traditional Approach | Graph OLAP |
|---------------------|------------|
| Hire a specialized team | Any analyst can use it |
| Weeks to set up | Ready in minutes |
| Complex data pipelines | Point at your data, it just works |
| Pay for servers 24/7 | Only runs when you're using it |
| Shared system (slows down for everyone) | Each analyst gets their own private workspace |

---

## The Technology (For Those Who Care)

<details>
<summary><strong>Click to expand technical details</strong></summary>

**Graph OLAP** bridges your **data warehouse** and **graph analytics**:

- Connects to Starburst, BigQuery, Snowflake, Databricks
- Exports data as optimized Parquet files to cloud storage
- Spins up isolated graph database pods per analyst
- Returns Cypher query results in milliseconds
- Auto-deletes pods after use — zero idle cost

**Production-Proven:** Running on Google Kubernetes Engine with real enterprise data.

| | Local Dev | Production |
|--|-----------|------------|
| **Setup** | `make deploy` | Same configuration |
| **Data** | Sample data included | Your real warehouse |
| **Security** | Simple auth | Enterprise JWT + IAM |
| **Scale** | Single laptop | Auto-scales to demand |

</details>

---

## See It In Action

**The difference is dramatic.** Here's how finding connected accounts looks:

| Traditional Database Query | Graph OLAP |
|---------------------------|------------|
| 15 lines of complex code | 3 lines, plain English-like |
| 4 minutes to run | 2 milliseconds |
| Easy to make mistakes | Visual, intuitive |
| Requires database experts | Any analyst can write it |

<details>
<summary><strong>Show me the actual code comparison</strong></summary>

**Traditional SQL** — 4 minutes on 10M rows:
```sql
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

**Graph Query** — 2 milliseconds:
```
MATCH (account)-[:TRANSFERRED*1..4]->(suspect)
WHERE account.id = 12345
RETURN suspect
```

The graph version reads almost like English: *"Find accounts connected through 1-4 transfers."*

</details>

---

## What You Get

| Capability | What It Means For You |
|------------|----------------------|
| **Works with your existing data** | Connects to your current databases — no migration needed |
| **Private workspace per person** | Your queries don't slow down anyone else |
| **Instant answers** | Results in milliseconds, not minutes |
| **Pay only when using** | System shuts down automatically when idle |
| **Self-service** | No IT tickets, no waiting for engineers |
| **Built-in analysis tools** | Find influencers, detect communities, calculate shortest paths |
| **Runs anywhere** | Your laptop for testing, cloud for production — same setup |

---

## How It Works

```
1. POINT     →  Tell the system which data tables contain your "things"
                (customers, accounts, products) and "connections" (transactions,
                relationships, dependencies)

2. CLICK     →  Request a graph workspace — takes about 10 seconds

3. ASK       →  Type questions like "find all accounts connected to X"
                — answers come back instantly

4. DONE      →  When you're finished, everything cleans up automatically
```

**Key point:** Each person gets their own private workspace. Your analysis doesn't affect anyone else, and theirs doesn't affect you.

---

## Who Uses This

| Industry | Example Question | Time Saved |
|----------|------------------|------------|
| **Banking & Finance** | "Which accounts are connected to this fraud suspect?" | Weeks → Seconds |
| **Pharma & Life Sciences** | "Which patients received this recalled drug batch?" | Days → Seconds |
| **Supply Chain** | "What products are affected if this supplier fails?" | Days → Instant |
| **Healthcare** | "Which doctors prescribed medications to this patient network?" | Hours → Seconds |
| **Retail** | "What else do customers like this one typically buy?" | Complex analysis → Simple query |
| **IT & Security** | "How did this user get access to this sensitive system?" | Manual audit → Instant trace |
| **HR & Compliance** | "Who reports to whom, and who approved each hire?" | Spreadsheet diving → Visual answer |

---

## Try It Yourself — 6 Interactive Demos

**No cloud account needed.** Everything runs on your laptop with sample data.

| Demo | What You'll Explore |
|------|---------------------|
| **Movie Network** | Which actors have worked together? Who are the most connected directors? |
| **Music Connections** | How are artists connected through albums and genres? |
| **E-commerce** | What products are frequently bought together? Customer recommendations? |
| **Sports Analytics** | Cricket team networks — players, matches, seasons |
| **Influence Analysis** | Find the most influential nodes, detect communities, shortest paths |

Each demo includes **interactive visualizations** — you'll see the connections as an actual network diagram you can explore.

![Interactive graph visualization — nodes and connections you can click and explore](graph-olap-local-deploy/docs-local/docs/assets/screenshots/ipl-graph.png)

---

## Already Running in Production

**This isn't a prototype or proof-of-concept.** The platform is deployed and running with real enterprise data:

- **Real users** querying real data daily
- **Automated deployment** — code changes go live automatically
- **Enterprise security** — proper authentication, no exposed credentials
- **Cost-efficient** — scales down to zero when not in use, scales up on demand
- **Two graph engines available** — users choose the best one for their task

---

## Architecture

<details>
<summary><strong>View system architecture (for technical teams)</strong></summary>

```text
┌─────────────────────────────────────────────────────────────────┐
│                      User Interface                              │
│   Browser / Jupyter Notebooks                                    │
└──────────────────────┬──────────────────────────────────────────┘
                       │
          ┌────────────▼─────────────┐
          │      Control Plane        │  The "brain" — coordinates
          │  - Receives requests      │  everything, manages all
          │  - Manages workspaces     │  analyst workspaces
          │  - Spawns graph engines   │
          └──────┬──────────┬────────┘
                 │          │
    ┌────────────▼──┐  ┌────▼──────────────────┐
    │   Database    │  │    Data Exporter       │
    │  (metadata)   │  │  Connects to your      │
    │               │  │  data warehouse        │
    └───────────────┘  └────────────────────────┘
                                  │
                        ┌─────────▼──────────┐
                        │   Cloud Storage     │  Efficient data
                        │   (data snapshots)  │  format for graphs
                        └─────────┬──────────┘
                                  │
          ┌───────────────────────▼──────────────────────┐
          │     Your Personal Graph Workspace             │
          │                                               │
          │   ┌──────────────┐  or  ┌──────────────────┐  │
          │   │  Engine A     │      │  Engine B        │  │
          │   │  (fast        │      │  (complex        │  │
          │   │   lookups)    │      │   analysis)      │  │
          │   └──────────────┘      └──────────────────┘  │
          │                                               │
          │   Ask questions → Get instant answers         │
          └───────────────────────────────────────────────┘
```

### Components

| Component | What It Does |
|-----------|--------------|
| **Control Plane** | Manages everything — receives your requests, creates workspaces, coordinates data flow |
| **Data Exporter** | Connects to your existing database (Starburst, BigQuery, etc.) and extracts the data you need |
| **Cloud Storage** | Stores data snapshots efficiently — can recreate your workspace anytime |
| **Graph Workspace** | Your private analysis environment — choose speed-optimized or analysis-optimized engine |
| **Jupyter Notebooks** | Interactive environment where you write queries and see visualizations |

### Technology Stack

| Layer | Technology |
|-------|------------|
| **Interface** | Jupyter Notebooks, REST API |
| **Graph Engines** | [FalkorDB](https://falkordb.com) (fast), [KuzuDB](https://kuzudb.com) (analytical) |
| **Data Warehouse** | Starburst, BigQuery, Snowflake, Databricks |
| **Infrastructure** | Kubernetes, Google Cloud |
| **Algorithms** | PageRank, Community Detection, Shortest Path, Centrality |

</details>

---

## Quick Start

**Try it on your laptop in 3 steps:**

```bash
# 1. Get the code
git clone https://github.com/your-org/graph-olap-local-deploy.git
cd graph-olap-local-deploy

# 2. Build and deploy (first time takes ~15 min, after that ~2 min)
make build && make deploy

# 3. Open the demo notebooks
open http://localhost:30081/jupyter/lab
```

**That's it.** No cloud account needed. No configuration. Sample data included.

| What You Can Access | URL |
|---------------------|-----|
| **Interactive Demos** | [localhost:30081/jupyter/lab](http://localhost:30081/jupyter/lab) |
| **API Documentation** | [localhost:30081/api/docs](http://localhost:30081/api/docs) |
| **Full Documentation** | [localhost:30082](http://localhost:30082) |

<details>
<summary><strong>Prerequisites (click to expand)</strong></summary>

You'll need:
- **Docker** — [Get Docker](https://docs.docker.com/get-docker/)
- **Local Kubernetes** — Choose one:
  - [OrbStack](https://orbstack.dev) (recommended for Mac)
  - [Docker Desktop](https://www.docker.com/products/docker-desktop/) with Kubernetes enabled
  - [Rancher Desktop](https://rancherdesktop.io)
  - [minikube](https://minikube.sigs.k8s.io/docs/start/)

</details>

---

## Common Commands

<details>
<summary><strong>View all available commands</strong></summary>

```bash
make build                      # Build all images
make build SVC=control-plane    # Build one specific service
make deploy                     # Deploy everything
make status                     # Check what's running
make logs SVC=control-plane     # View logs
make secrets                    # Set up credentials (for production data)
make teardown                   # Remove everything
```

</details>

---

## The Big Idea

**Traditional approach:** Your data sits in databases. When you need to understand connections, you hire consultants, build pipelines, wait weeks, pay for expensive always-on infrastructure.

**Graph OLAP approach:** Point at your existing data. Get a private workspace in seconds. Ask questions about connections. Pay nothing when you're not using it. Each analyst works independently.

The insight: **The hard part was never the graph database itself — it was getting your data into one.** We solved that.

---

## Learn More

| Resource | What You'll Find |
|----------|------------------|
| [**Interactive Demos**](#try-it-yourself--6-interactive-demos) | 6 notebooks you can run right now |
| [**Full Documentation**](http://localhost:30082) | Deep dives on every feature (after deploy) |
| [**Production Deployment Guide**](usecase/README.md) | 14 guides for deploying to Google Cloud |

---

## Contributing

We welcome contributions! See our contributing guidelines for details.

---

## License

Apache 2.0 — free to use, modify, and distribute. See [LICENSE](LICENSE).

---

<div align="center">

## Ready to See Connections?

**Stop digging through spreadsheets. Start seeing the patterns.**

[**Try the Demo**](#quick-start) — runs on your laptop, no cloud account needed

---

*Built for analysts who need answers, not infrastructure.*

</div>

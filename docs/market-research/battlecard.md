# Sales Battlecard

> Quick reference for competitive positioning and objection handling.

---

## The One-Liner

> **"Other graph databases charge you to wait. We only charge you to work."**

For technical audiences:

> **"PuppyGraph queries your warehouse. We materialize it. That's why they take seconds and we take milliseconds."**

---

## Quick Positioning

| What We Are | What We're NOT |
|-------------|----------------|
| Self-service graph analytics | A replacement for production graph DBs |
| In-house, privacy-first | SaaS-dependent |
| Ephemeral, per-analyst | Shared cluster |
| Zero idle cost | Always-on infrastructure |
| Analyst-friendly | Engineer-required |

---

## Objection Handling

### "We're evaluating Neo4j"

**Ask:** *"Do you have ETL engineers and an always-on budget?"*

**Say:** *"Neo4j is excellent for dedicated graph applications. But if your analysts need ad-hoc exploration without waiting for engineering, and you don't want to pay for idle clusters, we're faster to deploy and cheaper to run."*

**Key points:**
- Neo4j requires ETL pipelines — we use SQL mapping
- Neo4j clusters run 24/7 — we auto-delete after use
- Neo4j Aura Analytics (new) still lacks per-analyst isolation

---

### "We already use PuppyGraph"

**Ask:** *"How fast are your 4-hop traversal queries?"*

**Say:** *"PuppyGraph queries your warehouse directly, which is great for simple queries. But for multi-hop traversals, they're limited to warehouse speed — typically seconds. We materialize the graph in memory, so we return results in 2 milliseconds."*

**Key points:**
- PuppyGraph: query layer, warehouse speed (~2-5 seconds)
- Graph OLAP: materialized graph, memory speed (~2 milliseconds)
- We also have built-in algorithms (PageRank, Louvain, etc.)

---

### "Amazon Neptune is AWS-native"

**Ask:** *"Do you know Neptune's minimum monthly cost?"*

**Say:** *"Neptune can't scale to zero. Even if nobody queries for a month, you're paying ~$134 minimum. Our pods delete automatically — zero idle cost. Plus, we're not locked to AWS."*

**Key points:**
- Neptune minimum: ~$134/month idle
- Graph OLAP: $0 idle, pods auto-delete
- We run on any Kubernetes (AWS, GCP, Azure, on-prem)

---

### "TigerGraph is enterprise-grade"

**Ask:** *"What's your timeline and budget for the POC?"*

**Say:** *"TigerGraph is powerful but requires significant investment — high-memory hardware, graph expertise, months of setup. We deploy in 15 minutes with `make deploy`. You can have a working POC today."*

**Key points:**
- TigerGraph: months, $500k+, requires consultants
- Graph OLAP: minutes, runs on existing K8s, self-service

---

### "Databricks has GraphX"

**Say:** *"GraphX was deprecated in Spark 4.0 (November 2024). Databricks is moving away from graph processing. We're the modern replacement — but designed for analysts, not data engineers."*

**Key points:**
- GraphX is deprecated, no longer maintained
- GraphX was batch processing, we're interactive
- GraphX required Scala/Python, we're notebook-based

---

### "We need to keep data in-house"

**Say:** *"Perfect. Unlike Neo4j Aura, PuppyGraph Cloud, or Neptune, Graph OLAP runs entirely in your infrastructure. Data never leaves your network. Same platform on your laptop, your data center, or your private cloud."*

**Key points:**
- Full in-house deployment
- No SaaS dependency
- Compliance-friendly (banking, pharma, healthcare, government)

---

### "We're concerned about vendor lock-in"

**Say:** *"We use open source graph engines — FalkorDB and KuzuDB. Standard Cypher queries. Parquet files in your own GCS/S3. You can walk away anytime with zero migration cost."*

**Key points:**
- FalkorDB: open source (Redis-based)
- KuzuDB: open source (columnar)
- Standard Parquet format
- Standard Cypher query language

---

## Competitive Comparison Table

| Feature | Graph OLAP | Neo4j | PuppyGraph | Neptune | TigerGraph |
|---------|------------|-------|------------|---------|------------|
| Per-analyst isolation | **Yes** | No | No | No | No |
| Zero idle cost | **Yes** | No | No | No | No |
| In-house deployment | **Yes** | Partial | No | No | Yes |
| Sub-ms queries | **Yes** | Yes | No | Yes | Yes |
| No ETL required | **Yes** | No | Yes | No | No |
| Self-service | **Yes** | No | Partial | No | No |
| Open source engines | **Yes** | No | No | No | No |

---

## Target Segments (Where We Win)

| Segment | Why We Win |
|---------|-----------|
| **Mid-market companies** | Can't afford Neo4j/TigerGraph enterprise pricing |
| **Ad-hoc analysis teams** | Don't need always-on infrastructure |
| **Regulated industries** | Per-analyst isolation = compliance; in-house = data residency |
| **Cloud-cost-conscious** | Zero idle cost beats everyone |
| **Databricks shops** | GraphX deprecated, need modern replacement |

---

## Demo Script (15 minutes)

1. **[2 min]** Show the problem: 4-hop SQL query taking 4 minutes
2. **[2 min]** Run `make deploy` — everything comes up
3. **[3 min]** Open notebook, create mapping, spin up graph
4. **[3 min]** Run same query in Cypher — 2ms result
5. **[3 min]** Run PageRank, show visualization
6. **[2 min]** Show pod auto-delete, explain zero idle cost

**Key moment:** The 4 minutes vs 2 milliseconds comparison is the "wow" moment.

---

## Proof Points

- **Production-tested:** Running on GKE with enterprise data
- **6 demo notebooks:** Work out of the box, no cloud account needed
- **14 deployment guides:** Full GKE production documentation
- **Dual engine:** FalkorDB (fast lookups) + KuzuDB (algorithms)
- **Open source:** Apache 2.0 licensed

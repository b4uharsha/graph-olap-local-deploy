# Competitive Landscape Analysis

> Last updated: March 2025

## Market Overview

The graph database market is experiencing rapid growth driven by:
- AI/ML applications requiring knowledge graphs
- Fraud detection and AML compliance requirements
- Supply chain visibility and risk management
- Customer 360 and recommendation systems

**Market Size:** $3.3B (2025) → $11.4B (2030) at 27.9% CAGR

---

## Competitor Analysis

### 1. Neo4j

**What they do:** Market-leading dedicated graph database with Aura cloud offering.

| Aspect | Neo4j | Graph OLAP | Our Advantage |
|--------|-------|------------|---------------|
| Data loading | ETL required | SQL mapping | Weeks → Minutes |
| Idle cost | Always-on clusters | $0 when idle | 10x cheaper for ad-hoc |
| Isolation | Shared cluster | Per-analyst pods | Privacy + performance |
| Warehouse integration | Separate product (Aura Analytics) | Native | Single platform |
| Lock-in | Proprietary Cypher extensions | Open source engines | No lock-in |

**Neo4j Aura Graph Analytics (May 2025):** Their newest offering connects to warehouses but lacks per-analyst isolation and true scale-to-zero.

**How we win:** *"Neo4j is great if you have a dedicated team and always-on budget. We're for analysts who need answers today, not next quarter."*

---

### 2. PuppyGraph

**What they do:** Zero-ETL graph query engine that queries warehouses directly.

| Aspect | PuppyGraph | Graph OLAP | Our Advantage |
|--------|------------|------------|---------------|
| Architecture | Query layer over warehouse | Materialized in-memory graph | 10-100x faster multi-hop |
| 4-hop traversal | ~2-5 seconds | 2 milliseconds | Speed wins demos |
| Graph algorithms | Limited | Built-in (PageRank, etc.) | Analysts need algorithms |
| Isolation | Shared | Per-analyst pods | No noisy neighbor |
| Deployment | SaaS-first | In-house first | Data never leaves |

**How we win:** *"PuppyGraph queries your warehouse. We load it into memory. That's why they take seconds, we take milliseconds."*

---

### 3. Amazon Neptune

**What they do:** AWS managed graph database service.

| Aspect | Neptune | Graph OLAP | Our Advantage |
|--------|---------|------------|---------------|
| Minimum cost | ~$134/month (can't stop) | $0 (pods delete) | 100% cheaper idle |
| Scale to zero | No | Yes | Critical for ad-hoc |
| Setup | Complex IAM/VPC | `make deploy` | 10 min vs. days |
| Multi-cloud | AWS only | Any K8s | No cloud lock-in |
| Self-service | Requires AWS expertise | Notebook-based | Analyst-friendly |

**How we win:** *"Neptune charges you even when nobody's querying. We don't."*

---

### 4. TigerGraph

**What they do:** High-performance enterprise graph database for large-scale deployments.

| Aspect | TigerGraph | Graph OLAP | Our Advantage |
|--------|------------|------------|---------------|
| Target | Large enterprise ($$$) | Any size | SMB market open |
| Complexity | Requires graph experts | Self-service | No consultants |
| Hardware | High-memory dedicated | Ephemeral pods | Fraction of cost |
| Time to value | Months | Minutes | Faster POC wins |

**How we win:** *"TigerGraph is a jet engine. We're a Tesla — you just get in and drive."*

---

### 5. DataStax Graph (including Spark Analytics)

**What they do:** Enterprise graph on Apache Cassandra with TinkerPop/Gremlin. Includes OLAP-style analytics via SparkGraphComputer.

| Aspect | DataStax Graph + Spark | Graph OLAP | Our Advantage |
|--------|------------------------|------------|---------------|
| Expertise required | Cassandra + Spark + Gremlin | Cypher (SQL-like) | Much lower learning curve |
| Infrastructure | Always-on Cassandra + Spark cluster | Ephemeral K8s pods | 90%+ cost reduction |
| Query language | Gremlin (functional, complex) | Cypher (declarative, simple) | Easier adoption |
| Memory management | Spark executors (manual tuning) | In-memory graph (automatic) | No tuning required |
| OLAP queries | SparkGraphComputer (batch) | Real-time in-memory | Faster iteration |
| Per-analyst isolation | No (shared cluster) | Yes (dedicated pods) | No noisy neighbors |
| Setup | Days/weeks (Cassandra + Spark) | Minutes | 100x faster |
| Use case | Operational apps + batch analytics | Ad-hoc exploration | Different market |

**DataStax Spark Analytics Details:**
- Uses SparkGraphComputer for "deep queries" and "scan queries"
- Requires tuning: "executors with no more than 8 cores" recommended
- Memory-intensive: "substantial intermediate objects requiring garbage collection optimization"
- Best for teams already invested in Cassandra ecosystem

**How we win:** *"DataStax requires Cassandra + Spark expertise and always-on infrastructure. We require a SQL mapping and 10 seconds."*

**Source:** [DataStax Graph Analytics Documentation](https://docs.datastax.com/en/dse/6.9/graph/analytics/analytics-spark-computer.html)

---

### 6. Databricks GraphX

**What they do:** Spark-based graph processing (GraphFrames).

| Aspect | Databricks GraphX | Graph OLAP | Our Advantage |
|--------|-------------------|------------|---------------|
| Status | **Deprecated in Spark 4.0** | Active development | They're exiting |
| Query type | Batch processing | Interactive | Real-time answers |
| User | Data engineers | Analysts | Bigger market |
| Integration | Spark ecosystem | Warehouse-native | Simpler stack |

**How we win:** *"GraphX is deprecated. We're the replacement — but for analysts, not engineers."*

---

### 7. Splunk

**What they do:** Log analytics with graph visualization via ML Toolkit.

| Aspect | Splunk | Graph OLAP | Our Advantage |
|--------|--------|------------|---------------|
| Core function | Log analytics | Graph analytics | Purpose-built |
| Graph capability | Visualization only | Full graph DB | Real traversals |
| Self-service | Requires Splunk expertise | Notebook-based | Lower barrier |

**How we win:** *"Splunk visualizes graphs. We run graph algorithms and traversals."*

---

## Competitive Positioning Map

```
                        Always-On ◄──────────────────────► Ephemeral
                             │                                   │
    Shared Cluster ◄─────────┼───────────────────────────────────┼─────► Per-User
                             │                                   │
                             │   Neo4j                           │
                             │   Neptune    ┌─────────────────┐  │
                             │   TigerGraph │                 │  │
                             │              │  GRAPH OLAP     │  │
                             │   DataStax   │  (unique        │  │
                             │              │   position)     │  │
                             │              └─────────────────┘  │
                             │                                   │
    Query Layer Only ◄───────┼───────────────────────────────────┼─────► Materialized
                             │                                   │
                             │   PuppyGraph                      │
                             │   Neo4j Aura Analytics            │
                             │                                   │
```

---

## Summary: Our Unique Position

**Graph OLAP is the only solution that combines:**

1. **Ephemeral per-analyst workspaces** — True isolation, auto-cleanup
2. **Zero idle cost** — Pay nothing when not querying
3. **In-house deployment** — Data never leaves your network
4. **Materialized in-memory graphs** — Sub-millisecond queries
5. **Warehouse-native** — No ETL, SQL mapping only
6. **Self-service** — Analysts, not engineers
7. **Open source engines** — No vendor lock-in

**No competitor has all seven.**

---

## Sources

- [Mordor Intelligence - Graph Database Market](https://www.mordorintelligence.com/industry-reports/graph-database-market)
- [Neo4j Aura Graph Analytics Launch (May 2025)](https://neo4j.com/press-releases/aura-graph-analytics/)
- [PuppyGraph Zero-ETL](https://www.puppygraph.com/)
- [Amazon Neptune Pricing](https://aws.amazon.com/neptune/pricing/)
- [CloudFix - Neptune Idle Costs](https://cloudfix.com/blog/spend-less-on-aws-neptune-clean-up-idle-instances/)
- [Databricks GraphX Deprecation](https://docs.databricks.com/aws/en/machine-learning/graph-analysis)

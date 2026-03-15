# Cloud Provider Pricing Comparison

> How much do competitors charge, and how does Graph OLAP compare?

---

## Executive Summary

| Solution | Minimum Monthly Cost | Can Scale to Zero? | Pricing Model |
|----------|---------------------|-------------------|---------------|
| **Graph OLAP** | **$0** (your K8s) | **Yes** | Your infrastructure |
| Neo4j Aura | $65/month | No | Capacity-based |
| Amazon Neptune | ~$134/month | No | Instance-hours |
| TigerGraph Cloud | Contact sales | No | Compute + storage |
| PuppyGraph | Free tier available | Partial | Compute-based |

**Bottom line:** Graph OLAP is the only solution with true zero idle cost because it runs on your infrastructure and pods auto-delete.

---

## Detailed Pricing Breakdown

### 1. Neo4j Aura

**Source:** [Neo4j Pricing](https://neo4j.com/pricing/)

| Tier | Starting Price | Features |
|------|---------------|----------|
| AuraDB Free | $0 | 200k nodes, limited features |
| AuraDB Professional | $65/month | Production workloads |
| AuraDB Business Critical | $146/month | Enterprise features |
| Example: 4GB/0.8 CPU | $259.20/month | Mid-size deployment |

**Pricing model:** Capacity-based with hourly metering. Storage, IO, backup, and data transfer included.

**Key limitation:** Cannot scale to zero — minimum instance always running.

---

### 2. Amazon Neptune

**Source:** [Amazon Neptune Pricing](https://aws.amazon.com/neptune/pricing/)

| Instance Type | Hourly Cost | Monthly (730 hrs) |
|--------------|-------------|-------------------|
| db.t4g.medium | $0.084/hr | ~$61/month |
| db.r5.large | $0.348/hr | ~$254/month |
| db.r6g.large | $0.326/hr | ~$238/month |
| db.r8g.large | $0.274/hr | ~$200/month (16% savings) |

**Additional costs:**
- Storage: $0.10 per GB-month
- I/O: $0.20 per million requests (Standard) or included (I/O Optimized)
- Backup: $0.021 per GB-month

**Key limitation:**
- **Cannot scale to zero** — instances run 24/7
- Minimum viable HA setup (2 instances): ~$134/month idle
- Complex IAM/VPC setup required

---

### 3. TigerGraph Cloud (Savanna)

**Source:** [TigerGraph Pricing](https://www.tigergraph.com/savanna-pricing/)

| Component | Pricing Model |
|-----------|--------------|
| Compute | Based on workspace size + hours |
| Storage | Separate billing, GB-based |
| Data transfer | No charge (currently) |

**Enterprise pricing:** Contact sales — typically $50k-500k+/year for enterprise deployments.

**Key limitation:**
- No public pricing for enterprise tier
- High-memory requirements = expensive
- Requires graph expertise to deploy

---

### 4. PuppyGraph

**Source:** [PuppyGraph Pricing](https://www.puppygraph.com/pricing)

| Edition | Price | Features |
|---------|-------|----------|
| Developer | Free forever | POC, experimentation |
| Enterprise | Contact sales | Multi-instance, clustering, support |

**Pricing model:** Compute-based only — no storage fees (queries existing warehouse).

**Key advantage:** Zero storage cost (queries warehouse directly).

**Key limitation vs Graph OLAP:**
- Query layer only — no materialized graph
- Multi-hop traversals limited to warehouse speed (seconds, not milliseconds)
- SaaS-first model — data leaves your network

---

## Cost Comparison Scenarios

### Scenario 1: Ad-hoc Analysis Team (5 analysts, sporadic use)

| Solution | Monthly Cost | Notes |
|----------|-------------|-------|
| **Graph OLAP** | **~$50** | GCS storage only, pods auto-delete |
| Neo4j Aura | $325+ | 5 x $65 minimum |
| Neptune | $254+ | db.r5.large running 24/7 |
| TigerGraph | $5,000+ | Enterprise minimum |

**Graph OLAP saves: 80-99%**

---

### Scenario 2: Production Deployment (always-on, 100GB data)

| Solution | Monthly Cost | Notes |
|----------|-------------|-------|
| **Graph OLAP** | **~$300** | 3-node K8s + GCS |
| Neo4j Aura | $500+ | Business Critical tier |
| Neptune | $760+ | db.r5.xlarge HA |
| TigerGraph | $10,000+ | Enterprise |

**Graph OLAP saves: 40-97%**

---

### Scenario 3: Burst Analysis (heavy use 1 week/month)

| Solution | Monthly Cost | Notes |
|----------|-------------|-------|
| **Graph OLAP** | **~$75** | Pay only for active week |
| Neo4j Aura | $259+ | Charged full month |
| Neptune | $254+ | Charged full month |
| TigerGraph | $5,000+ | Charged full month |

**Graph OLAP saves: 70-99%**

---

## Why Graph OLAP Wins on Cost

### 1. Zero Idle Cost
```
Competitor: Instance runs 24/7 = 730 hours/month billed
Graph OLAP: Pod runs 2 hours/day = 60 hours/month compute, rest is pennies for GCS
```

### 2. Your Infrastructure
```
Competitor: Their markup on cloud resources
Graph OLAP: Your existing K8s cluster, no markup
```

### 3. Per-Analyst Isolation Without Per-Analyst Billing
```
Competitor: Each user = additional seat/capacity
Graph OLAP: Pods are ephemeral, share underlying infrastructure
```

### 4. No Data Transfer Costs
```
Competitor: Egress fees for querying your own data
Graph OLAP: Data stays in your network
```

---

## TCO Calculator

### Annual Cost Estimate

| Usage Pattern | Graph OLAP | Neo4j Aura | Neptune | Savings |
|--------------|------------|------------|---------|---------|
| Light (10 hrs/week) | **$600** | $3,100 | $3,050 | 80% |
| Medium (40 hrs/week) | **$2,400** | $6,200 | $6,100 | 61% |
| Heavy (always-on) | **$3,600** | $9,300 | $9,100 | 60% |
| Enterprise (HA) | **$7,200** | $18,600 | $18,200 | 60% |

*Assumes GKE/EKS standard pricing + GCS storage*

---

## Summary

| Factor | Graph OLAP Advantage |
|--------|---------------------|
| **Idle cost** | $0 vs $65-254/month minimum |
| **Burst workloads** | Pay only when running |
| **Multi-analyst** | No per-seat pricing |
| **Data transfer** | No egress fees |
| **Infrastructure** | Your existing K8s |
| **Vendor markup** | None |

**The math is simple:** If you don't need 24/7 always-on graph database, you're paying for idle time with every competitor. Graph OLAP is the only solution that truly scales to zero.

---

## Sources

- [Neo4j Pricing](https://neo4j.com/pricing/)
- [Amazon Neptune Pricing](https://aws.amazon.com/neptune/pricing/)
- [TigerGraph Savanna Pricing](https://www.tigergraph.com/savanna-pricing/)
- [PuppyGraph Pricing](https://www.puppygraph.com/pricing)
- [CloudFix - Neptune Idle Costs](https://cloudfix.com/blog/spend-less-on-aws-neptune-clean-up-idle-instances/)

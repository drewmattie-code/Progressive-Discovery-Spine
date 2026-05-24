# Progressive Discovery Spine — Specification

> **Status:** v1.0 · Drew Mattie · 2026-05-24
> **License:** [CC BY 4.0](LICENSE-CC-BY-4.0)

This is the full technical specification for the Progressive Discovery Spine pattern. The [README](README.md) is the elevator pitch; this document is the build reference.

---

## 1. Context — what PDS solves

The Model Context Protocol (MCP) gave the industry a clean, vendor-neutral way to expose tools to AI models. As a protocol, it works. As a deployment pattern, naive use of MCP falls apart at enterprise scale.

**MCP is necessary infrastructure for AI-to-enterprise integration. PDS is the architectural discipline that lets MCP deployments survive past prototype.** PDS does not replace MCP — it sits on top of it, treating MCP servers as the substrate and closing the production gaps the protocol does not define.

Four failure modes recur across teams:

1. **Context bloat.** Exposing every available tool consumes the context window before reasoning starts. Soria Parra has publicly described teams losing substantial portions of their context window to tool definitions before the model begins to reason.
2. **Hallucinated tool selection.** With unlimited tool choice, models pick wrong tools. The accuracy of tool selection degrades non-linearly with catalog size.
3. **Production gaps.** MCP defines no retries, no observability, no backpressure, no coordination. Production deployments need all four.
4. **Discovery anti-patterns.** Static tool exposure scales poorly. Dynamic retrieval — progressive discovery — is the emerging pattern, but the protocol doesn't define it.

PDS is the implementation discipline that addresses all four.

---

## 2. The architectural layer

PDS is a middleware layer between AI agents and backend systems. It is not a replacement for MCP; it sits on top of MCP and fills the gaps MCP leaves open.

```
┌──────────────────────────────────────────┐
│ YOUR AI AGENTS / PRODUCTS                │
│ (one or many; each declares its needs)   │
└──────────────────┬───────────────────────┘
                   ↓ semantic tool invocations
┌──────────────────────────────────────────┐
│ PROGRESSIVE DISCOVERY SPINE              │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │ search_tools(natural_language)     │  │
│  │       ↓                            │  │
│  │ Tool Search Index (pgvector)       │  │
│  │       ↓                            │  │
│  │ Scoped Tool Package (5–8 tools)    │  │
│  │       ↓                            │  │
│  │ Semantic Entity Tools              │  │
│  │       ↓                            │  │
│  │ Gateway: retry / backpressure /    │  │
│  │  observability / audit / tenancy   │  │
│  │       ↓                            │  │
│  │ Per-Tenant Session Cache           │  │
│  └────────────────────────────────────┘  │
└──────────────────┬───────────────────────┘
                   ↓ translated calls
┌──────────────────────────────────────────┐
│ MCP CONNECTOR POOL                       │
│ (one connector per backend system)       │
└──────────────────┬───────────────────────┘
                   ↓
┌──────────────────────────────────────────┐
│ BACKEND SYSTEMS                          │
│ ERP · CRM · DBs · custom APIs            │
└──────────────────────────────────────────┘
```

Every arrow through PDS is observable, tenant-scoped, retry-handled, and audit-logged.

---

## 3. The 10 principles

### 3.1 — Semantic entity tools, not table tools

**Problem.** A naive implementation exposes `po_header`, `po_item`, `vendor_master`, `vendor_scores`, `vendor_rebate_tiers` as separate tools. The agent reasons about which tables to join. Joins drift. Models hallucinate column names.

**Pattern.** Expose business-meaningful composed tools. The tool *is* the business query:

- `search_open_pos(supplier?, date_range?, value_threshold?, customer?)` returns composed PO objects with line items, supplier scorecard, contract references, and active rebate tier in one response.
- `get_supplier_risk_scorecard(supplier_id)` returns a composed score with component breakdown, news sentiment, delivery variance, and financial-stability signals.
- `reconcile_rebate(supplier, period)` returns the computed reconciliation including contract clauses, tier analysis, and any discrepancy dollar amount.

**Implementation.** Every connector's tool manifest is authored in terms of your normalized data model. Connector-specific SQL or API calls are hidden behind the semantic tool name. The agent never sees `LIFNR` or `PO_HEADERS_ALL`.

**Anti-pattern.** Auto-generating tools from database schema. You will get one tool per table, the agent will compose them, and joins will hallucinate.

---

### 3.2 — Workflow-scoped tool packages

**Problem.** A real enterprise might surface 200+ business-meaningful tools — suppliers, contracts, rebates, inventory, orders, shipments, receipts, returns, quality, compliance, sales, quotes, customers, forecasts, BOM, routings, WIP, labor, cost accounting. Loading all of them into every agent context is wasteful.

**Pattern.** Pre-define tool packages per agent or product. Each package is the minimal tool set needed for that agent's work.

| Pack | Tools loaded | Used by |
|---|---|---|
| Inventory-exception pack | `search_open_pos`, `get_inventory_position`, `get_stockout_risk`, `search_exceptions`, `get_supplier_lead_time`, `flag_low_coverage_skus` | Exception-routing agent |
| Contract-workflow pack | `get_vendor_contract`, `search_open_workflows`, `get_rebate_tier`, `draft_letter_of_acceptance`, `get_dispute_history`, `calculate_penalty` | Contract / LOA agent |
| Scenario-simulation pack | `simulate_disruption`, `get_supplier_exposure`, `project_stockout_cascade`, `get_bom_dependency`, `estimate_delivery_variance` | Scenario / forecasting agent |
| Operations-overview pack | `get_customer_supplier_map`, `get_site_locations`, `get_live_risk_events`, `get_chokepoint_status` | Operations dashboard agent |
| Sales-enablement pack | `get_sales_pipeline`, `search_quotes`, `get_customer_contract`, `get_opportunity_detail`, `get_account_exposure` | Sales agent |

Each pack is 5–8 tools. The names above are illustrative — name your packs after your agents.

**Implementation.** On session creation, the agent tells PDS which pack(s) it needs. PDS loads only those definitions into context.

---

### 3.3 — Tool search as the default entry point

**Problem.** Pre-defined packs still require product-time decisions ("which pack does this task need?"). Sometimes the agent needs a tool not in its pack.

**Pattern.** Always expose one meta-tool as the default:

```python
search_tools(query: str, limit: int = 5) -> list[ToolDefinition]
```

The agent calls `search_tools("which customers have exposure to a single supplier")`. PDS queries its internal tool index (pgvector embedding over tool descriptions + entity names + common query phrasings) and returns the 5 most relevant tools. The agent then invokes those.

**Why this works.**

- **Context cost is bounded.** One tool (`search_tools`) stays loaded permanently. Additional tools load dynamically.
- **Fuzzy matching is forgiving.** "How do I find open POs for X" returns `search_open_pos`. The agent doesn't need to know the exact tool name.
- **Tool discovery scales to thousands** without exceeding the context budget.

**Implementation.** pgvector index over tool manifests. Tool descriptions should include natural-language query examples as training data ("Users asking about rebate reconciliation invoke this tool"). Re-embed on every tool release.

---

### 3.4 — Normalized data model as abstraction

**Problem.** Customer A runs Oracle EBS. Customer B runs SAP S/4. Customer C runs Epicor. Their schemas are different. Their field names are different. Their rebate structures are different.

**Pattern.** Define a normalized data model (CDM) once. Expose tools in CDM terms. Each connector translates CDM calls into the customer's actual backend schema under the hood.

**What this means for the agent:**

- Agent operates on `Supplier`, `PurchaseOrder`, `Invoice`, `Contract`, `InventoryPosition` — semantic entities
- Agent does **not** see SAP's `LIFNR`, Oracle's `PO_HEADERS_ALL`, or Epicor's `SupplierID.Key`
- Tool signature is identical across customers; the connector handles translation

**Implementation.** Domain-driven design helps here. Model the entities first, then build connectors that fulfill the contract. Never expose vendor schemas to the agent.

---

### 3.5 — Gateway as the control layer

**Problem.** MCP doesn't define retries, observability, backpressure, or coordination. Without these, production deployments fail.

**Pattern.** Every tool call routes through a gateway that adds:

| Capability | Implementation |
|---|---|
| **Retry with backoff** | Exponential backoff on 429 / 502 / 503. Max 3 retries. Honor `Retry-After`. |
| **Circuit breaker** | If a backend endpoint fails N times in a window, gateway "opens" and returns cached data with `stale: true` flag. |
| **Backpressure** | Per-tenant rate limits (e.g., 100 calls/min to a given backend). Excess queued, not dropped. |
| **Observability** | Every tool call logged: tool name, params (PII-redacted), latency, response size, cache hit/miss, tenant ID, agent session ID, business outcome tag. |
| **Tenant isolation** | Every call carries `tenant_id`; gateway rejects cross-tenant access. Per-tenant encryption keys. |
| **Audit trail** | Immutable append log of every tool call. SOC 2 Type II compliant. Tenants can download their own audit history. |
| **Schema validation** | Enforce CDM schemas on every response. Malformed backend data surfaces as a warning, not a crash. |

The gateway is the missing half of MCP. Soria Parra explicitly identifies this gap; PDS fills it.

---

### 3.6 — Per-session caching with freshness metadata

**Problem.** Backend calls are slow (500–2000ms is typical). Within a single agent session investigating one workflow, the agent may call `get_supplier` 30 times. Thirty calls × one second each = thirty seconds wasted on data that didn't change.

**Pattern.** Per-session in-memory cache keyed by `(tenant_id, session_id, tool_name, params_hash)`. Default TTL 10 minutes. Invalidate on upstream CDC events (if the supplier master changes mid-session, flush the session cache entry for that supplier).

Every cached response carries metadata:

```json
{
  "data": { ... },
  "fetched_at": "2026-05-24T17:22:14Z",
  "source": "cache",
  "cache_age_seconds": 180,
  "freshness_policy": "< 30 min = current for this entity"
}
```

**Why metadata matters.** The agent can make intelligent decisions. If it's drafting a memo based on a four-minute-old Supplier record, it shrugs. If it's computing live cash exposure, it forces a cache bypass. Agents read the metadata and adapt.

---

### 3.7 — Tenant-scoped tool catalogs

**Problem.** Tenant A runs Oracle. Tenant B runs SAP. Oracle-specific tools don't apply to Tenant B. Exposing both to an agent servicing Tenant B is context pollution and a latent leak surface.

**Pattern.** On session start, PDS resolves the active tenant's backend profile and exposes only matching tools. From the agent's point of view, the tool is just `search_open_pos`; under the hood the Oracle connector handles it for Tenant A and the SAP connector handles it for Tenant B.

**Implementation detail.** Tool manifest is dynamically constructed per session. PDS resolves `(tenant_id, enabled_connectors) → active_tools` and returns the result.

---

### 3.8 — Failure-aware tool descriptions

**Problem.** An agent that doesn't understand tool SLAs will call a 2-second tool in a loop when a 50ms alternative exists. Agents need to pick tools intelligently.

**Pattern.** Every tool description in the tool manifest includes SLA metadata the agent can read:

```json
{
  "name": "search_open_pos",
  "description": "Search purchase orders by supplier / date range / value threshold.",
  "sla": {
    "p50_latency_ms": 600,
    "p95_latency_ms": 2000,
    "freshness_seconds": 300,
    "cost_units": 1,
    "availability_windows": "24x7 except customer batch windows",
    "known_batch_windows": ["02:00-04:00 UTC daily"]
  },
  "failure_modes": [
    "SAP IDoc queue saturation may cause >5s latency",
    "Returns cached data with staleness flag during batch windows"
  ]
}
```

**Value.** Agent planners route around degradation. If a connector is in a batch window, the agent picks a CDC-cached alternative or delays the query. If a tool is expensive (high `cost_units`), the agent batches calls.

A worked example of a tool manifest with SLA metadata is in [`examples/tool-manifest.example.json`](examples/tool-manifest.example.json).

---

### 3.9 — Action menu as curated invocation

**Problem.** Free-form agent tool selection is error-prone. Every ungated tool invocation is a risk — wrong tenant, wrong parameters, wrong context.

**Pattern.** Every entity in the UI surfaces a right-click Action Menu exposing a curated, pre-parameterized set of 6 actions. Example: right-click a Supplier:

1. **Draft letter of acceptance** → invokes `draft_letter_of_acceptance(supplier_id=<this>, contract=<current>)`
2. **Reconcile current rebate** → invokes `reconcile_rebate(supplier_id=<this>, period=<current_quarter>)`
3. **Project stockout cascade** → invokes `project_stockout_cascade(supplier_id=<this>, horizon=90d)`
4. **Get risk scorecard** → invokes `get_supplier_risk_scorecard(supplier_id=<this>)`
5. **Search open POs** → invokes `search_open_pos(supplier_id=<this>)`
6. **Escalate to CFO** → invokes `escalate_to_cfo(supplier_id=<this>, urgency=<selected>)`

Every parameter is bound from UI context. Zero hallucination surface.

This is the reduce-the-decision-surface principle Soria Parra has discussed publicly, pushed to its logical conclusion. PDS makes the pattern uniformly implementable across every product surface in your system.

See [`examples/action-menu.md`](examples/action-menu.md) for the UI pattern.

---

### 3.10 — Natural-language entry as the front door

**Problem.** Users shouldn't have to know which product or sub-system to enter to accomplish a task. "Find customers exposed to a major vendor's lead-time extension" is not a sub-product question — it's an organizational question.

**Pattern.** Expose a single natural-language query bar as the front door to the entire system. User types a query. The query bar calls PDS `search_tools(query)`. PDS retrieves relevant tools. An agent runs them. A synthesized answer comes back.

This is the user-facing manifestation of progressive discovery. Instead of exposing 200+ tools to every user, expose one text box. The spine resolves the rest.

**Implementation.** The query bar is a thin orchestration layer on top of PDS. The heavy lifting (tool search, retrieval, execution, synthesis) is PDS. The query bar handles UX and conversation state.

---

## 4. SLAs and success metrics

| Metric | Target | Rationale |
|---|---|---|
| Tool invocation p50 latency (cached) | < 50 ms | Cache must be lightweight |
| Tool invocation p95 latency (live) | < 2,000 ms | Most enterprise systems clear this |
| Cache hit rate per session | > 60% | Proves cache is effective |
| Cross-tenant leakage incidents | 0 | Non-negotiable security requirement |
| Audit log completeness | 100% | SOC 2 Type II prerequisite |
| Context window used by tool definitions | < 5% of window | Progressive discovery is the point |
| Time from tenant onboarding to first successful tool call | < 30 min | Business outcome metric |
| Tools available per tenant (via search) | > 200 | Coverage |
| Tools loaded into agent context by default | 5–8 | Efficiency |

---

## 5. Build sequence

PDS is built in the following sequence from skeleton to first reference deployment. Each step depends on the previous one. Pace varies by team and tooling; the sequence does not.

| Step | Deliverable | Why |
|---|---|---|
| 1 | Tool manifest format · `search_tools` over pgvector · basic gateway with retry/backoff | Skeleton has to be observable from day one |
| 2 | First connector exposed through PDS with 3–5 semantic tools · end-to-end trace | Proves the abstraction holds for one real backend |
| 3 | Per-tenant session cache · audit log · first internal consumer | Adds the gateway capabilities and lights up a real agent |
| 4 | Workflow-scoped packages · second and third agent consumers | Forces the pack abstraction to be real |
| 5 | Second connector (different backend) | Proves cross-system semantic-tool abstraction |
| 6 | SLA metadata · failure-mode descriptions · circuit breaker | Production-readiness |
| 7 | First end-to-end production reference deployment | Business outcome |
| 8 | Spec / one-pager / case study | Compounds future adoption |

---

## 6. Anti-patterns to avoid

| Anti-pattern | Why it breaks | What to do instead |
|---|---|---|
| Auto-generated tools from DB schema | One tool per table; agent composes; joins hallucinate | Hand-author semantic-entity tools |
| Static tool exposure (all tools loaded all sessions) | Context blowout | `search_tools` + packs |
| Application-layer tenant isolation | Single bug = cross-tenant leak | Enforce at protocol/gateway layer |
| MCP-only deployment (no gateway) | No retries, no audit, no backpressure | Add a gateway in front of every connector |
| Raw cache without freshness metadata | Agent can't decide when to bypass | Return `fetched_at` + `cache_age_seconds` + `freshness_policy` on every response |
| Free-form parameter selection from UI | Hallucinated supplier IDs, wrong tenants | Bind parameters from UI context (Action Menu pattern) |
| One tool catalog for all tenants | Pollution and leak surface | Tenant-scoped catalogs resolved at session start |

---

## 7. Compatibility with existing standards

PDS is compatible with — and built on top of — these standards:

- **MCP (Model Context Protocol)** — Connectors at the bottom of the stack are MCP servers. PDS is the layer above MCP, not a replacement for it.
- **OpenAPI / JSON Schema** — Tool manifests use JSON Schema for parameter and response shapes.
- **OpenTelemetry** — Gateway observability emits OTel-compatible traces.
- **SOC 2 / ISO 27001 audit requirements** — The gateway's audit log is designed to satisfy these.

---

## 8. References

- David Soria Parra, "The Future of MCP," MCP Dev Summit NA 2026 ([YouTube](https://youtu.be/v3Fr2JR47KA))
- Shiftmag interview, "MCP co-creator on What Breaks MCP at Scale" ([article](https://shiftmag.dev/mcp-co-creator-explains-why-mcp-needs-more-than-the-protocol-to-scale-9041/))
- MCP Dev Summit NA 2026 recap ([AAIF](https://aaif.io/blog/mcp-is-now-enterprise-infrastructure-everything-that-happened-at-mcp-dev-summit-north-america-2026/))
- Model Context Protocol specification ([modelcontextprotocol.io](https://modelcontextprotocol.io))

---

## 9. Versioning

This specification follows semantic versioning. Breaking changes to the conceptual model bump the major version; new principles or refinements bump the minor. Editorial fixes bump the patch.

- **v1.0** — initial public release (2026-05-24)

---

## 10. Author

[Drew Mattie](https://www.linkedin.com/in/drew-mattie-88084826/) · SaaSquach AI Labs (a division of Charles & Roe Inc.) · 2026

PDS was coined and developed at SaaSquach AI Labs (a division of Charles & Roe Inc.) as the architectural foundation for AI products operating against enterprise systems at scale. This specification is released as open documentation under [CC BY 4.0](LICENSE-CC-BY-4.0) so the pattern can be adopted, adapted, and built upon — with attribution.

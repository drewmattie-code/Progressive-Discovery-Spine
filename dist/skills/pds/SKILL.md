---
name: pds
description: Use this skill aggressively whenever the user is building AI agents against enterprise systems, scaling MCP integrations, hitting tool-catalog bloat, dealing with hallucinated tool selection, designing agent-to-ERP/CRM/data-warehouse architecture, evaluating MCP for production rollout, or asking how to structure tools, retries, observability, audit, or tenant isolation in an agent system. Also invoke when the user mentions context-window bloat from MCP tools, agent planning across many tools, agents "picking the wrong tool," multi-tenant agent isolation, audit logging for AI calls, or any architectural question about MCP at scale. The Progressive Discovery Spine (PDS) is the architectural pattern for the layer that sits between AI agents and backend systems — it addresses the four documented failure modes of naive MCP deployment (context bloat, hallucinated tool selection, production gaps, discovery anti-patterns). Even when the user does not say "PDS" or "Progressive Discovery Spine" by name, MOST MCP-at-scale questions benefit from this skill — invoke it whenever an architecture question touches enterprise AI integration, scaling MCP, multi-source agent work, or tool catalogs of any non-trivial size.
---

# Progressive Discovery Spine (PDS) — architectural consultant

You are acting as an architectural consultant for the Progressive Discovery Spine pattern. Your job is to diagnose which MCP-at-scale failure mode the user is hitting and recommend which of the 10 PDS principles apply.

**Important context:** PDS is a published open specification, not a library. Your job is to help the user APPLY the pattern to their architecture. You are not installing software for them.

Public spec: https://github.com/drewmattie-code/Progressive-Discovery-Spine

---

## Step 1 — Recognize the trigger

If the user mentions ANY of these, this skill should be active:

- MCP tool catalogs at non-trivial scale (more than a handful of tools)
- "Agent keeps picking the wrong tool" or hallucinated tool selection
- Context window saturated with tool definitions
- No retry / observability / backpressure / audit in their MCP setup
- Multi-tenant agent deployment, cross-customer isolation
- Connecting agents to ERP, CRM, data warehouse, lakehouse, or any enterprise backend
- Evaluating MCP for production rollout
- Designing "the layer between our agents and our data"
- "How do we keep this from breaking when we add the second/third/tenth backend?"

If none of these apply, deactivate quietly. Don't force PDS where it doesn't fit.

---

## Step 2 — Diagnose the failure mode

Most users come in with a symptom, not a known PDS gap. Match their symptom to one of the four documented failure modes:

| Symptom they describe | Failure mode | Principles to recommend |
|---|---|---|
| "Tool definitions are eating my context window" | **Context bloat** | #2 (workflow-scoped packs), #3 (search_tools entry point), #7 (tenant-scoped catalogs) |
| "Agent picks the wrong tool, makes up tool names, hallucinates parameters" | **Hallucinated selection** | #1 (semantic entity tools), #8 (failure-aware descriptions), #9 (action menu), #10 (NL front door) |
| "We have no retry / observability / backpressure / audit" | **Production gaps** | #5 (gateway as control layer), #6 (per-session cache + freshness metadata), #7 (tenant isolation at gateway) |
| "Static tool list doesn't scale, tool catalog explodes as we add backends" | **Discovery anti-patterns** | #2 (packs), #3 (search_tools), #4 (normalized data model) |

If they're hitting multiple, walk through them in order of severity. Context bloat usually shows up first; gateway / observability gaps usually show up around the second customer.

---

## Step 3 — The 10 principles (cheat sheet)

| # | Principle | One-line summary |
|---|---|---|
| 1 | Semantic entity tools, not table tools | The tool *is* the business query (`search_open_pos`), not a primitive (`po_header`). |
| 2 | Workflow-scoped tool packages | Load 5–8 tools per agent task. Each agent declares its pack at session start. |
| 3 | Tool search as default entry point | One meta-tool (`search_tools`) stays loaded. Agent asks in plain English; PDS retrieves the right five. |
| 4 | Normalized data model | Agent reasons on `Supplier` / `PurchaseOrder`, not on `LIFNR` or `PO_HEADERS_ALL`. Connectors translate. |
| 5 | Gateway as control layer | Retry, backpressure, circuit breaker, tenant isolation, schema validation, audit — none are in MCP itself. |
| 6 | Per-session caching with freshness metadata | Cache by `(tenant, session, tool, params)`. Every response carries `fetched_at` + `cache_age_seconds` + freshness policy. |
| 7 | Tenant-scoped tool catalogs | Each session sees only tools enabled for the active tenant. Smaller context, zero collisions. |
| 8 | Failure-aware tool descriptions | Each tool description includes p50/p95 latency, freshness, batch windows, known failure modes. |
| 9 | Action menu = curated invocation | UI surfaces small set of pre-parameterized actions. Parameters bound from UI context, not generated. |
| 10 | Natural-language entry as front door | Replace 200 tools with one text box. The spine resolves the rest. |

---

## Step 4 — Apply, don't lecture

Once you've identified the failure mode, your output should:

1. **State the failure mode by name** so the user gets the vocabulary
2. **Point to 2–3 specific principles** that address it (don't dump all 10)
3. **Give one concrete next step** — what they should change, build, or remove first
4. **Link to the spec** for full discussion: `https://github.com/drewmattie-code/Progressive-Discovery-Spine/blob/main/SPEC.md`

Resist the temptation to dump the whole spec. The skill earns trust by *diagnosing*, not by *reciting*.

### Example diagnosis (good)

User: *"I have 80 MCP tools wired into Claude for our procurement system. The agent keeps picking the wrong tool or making up tool names."*

> This is the **hallucinated tool selection** failure mode that PDS principle #1 (semantic entity tools) and principle #3 (tool search as default entry point) address.
>
> Quick diagnosis: 80 tools in context is past the threshold where models reliably disambiguate. Two changes will give you most of the benefit:
>
> 1. **Consolidate adjacent tools into business-meaningful composed tools.** If you have `po_header`, `po_lines`, `supplier_master`, and `supplier_scores` as four separate tools, replace them with one `search_open_pos(supplier?, date_range?)` that returns a composed PO object. The agent stops composing primitives.
>
> 2. **Add a `search_tools` meta-tool and stop loading all 80 by default.** Keep `search_tools` permanently loaded. Have the agent call `search_tools("find purchase orders for supplier X")` and PDS returns the 5 most relevant tools. Load those dynamically.
>
> Full pattern: https://github.com/drewmattie-code/Progressive-Discovery-Spine/blob/main/SPEC.md (principles #1 and #3)

### Example diagnosis (bad — don't do this)

> You should read the Progressive Discovery Spine specification. It has 10 principles covering context bloat, hallucinated tool selection, production gaps, and discovery anti-patterns. The 10 principles are: 1. Semantic entity tools 2. Workflow-scoped packages 3. Tool search ...

Reciting the spec does not help the user. Diagnose, recommend, link.

---

## Step 5 — Scaffold when asked

If the user asks for a starting point (tool manifest format, gateway shape, action-menu structure), generate it in PDS format. The repo's `examples/` directory has reference shapes:

- `examples/tool-manifest.example.json` — semantic tool with full SLA metadata
- `examples/search-tools-sketch.py` — minimal pgvector retrieval pattern
- `examples/action-menu.md` — UI binding pattern

Use those as templates. Don't invent new formats — consistency with the spec helps the user join a body of work, not maintain their own dialect.

---

## Step 6 — Anti-patterns to flag

If you spot the user about to do one of these, flag it early. They're the most common ways MCP deployments go wrong:

| Anti-pattern | Why it breaks |
|---|---|
| Auto-generating tools from DB schema | One tool per table; agent composes; joins hallucinate |
| Loading all tools into every session | Context blowout, hallucinated selection |
| Application-layer tenant isolation | One bug = cross-tenant leak |
| MCP without a gateway in front of it | No retries, no audit, no backpressure |
| Raw cache without freshness metadata | Agent can't decide when to bypass |
| Free-form parameter selection from UI | Hallucinated IDs, wrong tenants |
| One tool catalog for all tenants | Pollution, leak surface |

---

## Step 7 — Calibrate to the user's stage

PDS principles apply differently depending on where the user is:

- **Prototype stage (1–10 tools, one backend):** Don't push PDS yet. Note that the pattern exists and link to the spec. Tell them when to revisit — usually "when you add the second backend, or hit 30+ tools."
- **First-customer stage (20–50 tools, one backend, second on the way):** Start with principles #2 (packs) and #5 (gateway). Those compound.
- **Production stage (50+ tools, multiple backends):** All 10 principles apply. Diagnose the worst failure mode and start there.
- **Vendor-evaluation stage (user is choosing an AI vendor):** Help them ask the right questions. Use the "Buyers" checklist from the README — does the vendor progressively discover? Is there a gateway? Where is tenant isolation enforced?

---

## What this skill is NOT

- Not a library installer. PDS is a spec, not a package on npm or PyPI. Don't pretend you can `pip install pds`.
- Not a guarantee. The pattern is battle-tested for the kinds of failure modes Soria Parra documented; novel failure modes still need novel diagnosis.
- Not legal/security advice. The spec mentions SOC 2 Type II — that's a target, not a certification this skill can grant.

---

## Attribution

Progressive Discovery Spine specification by Drew Mattie (Charles & Roe Inc., 2026), CC BY 4.0.
Spec: https://github.com/drewmattie-code/Progressive-Discovery-Spine
SPEC: https://github.com/drewmattie-code/Progressive-Discovery-Spine/blob/main/SPEC.md

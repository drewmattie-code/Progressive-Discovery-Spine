#!/usr/bin/env python3
"""
PDS runnable example: search-first tool discovery.
==================================================

Demonstrates the core Progressive Discovery Spine mechanic end to end, with no
dependencies (stdlib only). It:

  1. Builds a realistic tenant catalog of ~500 tool manifests.
  2. Validates a sample of them against schema/tool-manifest.v1.json.
  3. Runs search_tools(query) -> top-K, the single entry point an agent calls.
  4. Validates the search response against schema/tool-search-response.v1.json.
  5. Prints the context reduction: full catalog vs the handful surfaced.

This is the point of PDS principle #3: an agent never receives the whole
catalog, only the few tools its task needs. Run it:

    python3 examples/discover.py

License: MIT
"""

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SCHEMA = HERE.parent / "schema"


# ---------------------------------------------------------------------------
# Minimal JSON Schema validator (stdlib only).
# Covers the subset used by the Spine schemas: type, required, properties,
# items, enum, additionalProperties:false. For full validation use jsonschema
# (Python) or ajv (JS); this keeps the example dependency-free.
# ---------------------------------------------------------------------------

_TYPES = {
    "object": dict, "array": list, "string": str,
    "boolean": bool, "number": (int, float), "integer": int,
}


def validate(instance, schema, path="$"):
    errs = []
    t = schema.get("type")
    if t:
        py = _TYPES[t]
        # bool is a subclass of int; keep them distinct
        if t in ("number", "integer") and isinstance(instance, bool):
            errs.append(f"{path}: expected {t}, got boolean")
            return errs
        if not isinstance(instance, py):
            errs.append(f"{path}: expected {t}, got {type(instance).__name__}")
            return errs
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: {instance!r} not in {schema['enum']}")
    if t == "object" and isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errs.append(f"{path}: missing required '{req}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errs.append(f"{path}: unexpected property '{key}'")
        for key, sub in props.items():
            if key in instance:
                errs += validate(instance[key], sub, f"{path}.{key}")
    if t == "array" and isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            errs += validate(item, schema["items"], f"{path}[{i}]")
    return errs


# ---------------------------------------------------------------------------
# Build a realistic catalog
# ---------------------------------------------------------------------------

DOMAINS = {
    "procurement": (["search", "create", "approve", "cancel", "expedite"],
                    ["purchase_order", "requisition", "supplier", "rfq", "contract"]),
    "finance": (["post", "reconcile", "forecast", "close", "audit"],
                ["invoice", "journal_entry", "ledger", "payment", "budget"]),
    "inventory": (["check", "reserve", "transfer", "count", "replenish"],
                  ["stock_level", "warehouse_bin", "lot", "shipment", "sku"]),
    "hr": (["lookup", "onboard", "schedule", "approve", "report"],
           ["employee", "time_off", "shift", "expense", "headcount"]),
    "sales": (["quote", "forecast", "score", "renew", "escalate"],
              ["opportunity", "account", "lead", "order", "ticket"]),
    "logistics": (["track", "route", "rate", "book", "dispatch"],
                  ["shipment", "carrier", "lane", "load", "dock_appointment"]),
}


def make_manifest(verb, noun, domain):
    name = f"{verb}_{noun}"
    return {
        "name": name,
        "version": "1.0.0",
        "description": f"{verb.capitalize()} {noun.replace('_', ' ')} records in the {domain} domain.",
        "intent_examples": [
            f"{verb} the {noun.replace('_', ' ')}",
            f"help me {verb} a {noun.replace('_', ' ')}",
        ],
        "parameters": {"type": "object", "properties": {f"{noun}_id": {"type": "string"}}},
        "returns": {"type": "object", "description": f"A composed {noun} envelope."},
        "sla": {"p95_latency_ms": 2000, "freshness_seconds": 300, "cost_units": 1},
        "tenant_scope": {"required": True, "enforced_at": "gateway"},
    }


def build_catalog():
    catalog = []
    # the real, hand-written manifest ships in this folder
    real = json.loads((HERE / "tool-manifest.example.json").read_text())
    catalog.append(real)
    for domain, (verbs, nouns) in DOMAINS.items():
        for verb in verbs:
            for noun in nouns:
                m = make_manifest(verb, noun, domain)
                if m["name"] != real["name"]:
                    catalog.append(m)
    return catalog


# ---------------------------------------------------------------------------
# search_tools: the single entry point. Token-overlap stand-in for the
# embedding search a real deployment runs (pgvector etc.).
# ---------------------------------------------------------------------------

def _tokens(text):
    return {t for t in "".join(c.lower() if c.isalnum() else " " for c in text).split() if len(t) > 2}


def _searchable_text(m):
    parts = [m["name"].replace("_", " "), m["description"]]
    parts += m.get("intent_examples", [])
    parts += list(m.get("parameters", {}).get("properties", {}).keys())
    return " ".join(parts)


def search_tools(query, catalog, tenant_id="acme-corp", k=5):
    q = _tokens(query)
    scored = []
    for m in catalog:
        overlap = len(q & _tokens(_searchable_text(m)))
        if overlap:
            scored.append((overlap, m))
    scored.sort(key=lambda x: (-x[0], x[1]["name"]))
    top = scored[:k]
    return {
        "query": query,
        "tenant_id": tenant_id,
        "catalog_size": len(catalog),
        "returned": len(top),
        "results": [
            {"name": m["name"], "description": m["description"],
             "score": float(score), "sla": m["sla"]}
            for score, m in top
        ],
    }


def _tokens_estimate(obj):
    # rough: ~4 chars per token
    return len(json.dumps(obj)) // 4


def main():
    manifest_schema = json.loads((SCHEMA / "tool-manifest.v1.json").read_text())
    response_schema = json.loads((SCHEMA / "tool-search-response.v1.json").read_text())

    catalog = build_catalog()
    print(f"Catalog: {len(catalog)} tool manifests for this tenant.\n")

    # 1) validate manifests against the schema
    bad = 0
    for m in catalog:
        errs = validate(m, manifest_schema)
        if errs:
            bad += 1
            print(f"  INVALID {m.get('name')}: {errs[:2]}")
    print(f"Manifest validation: {len(catalog) - bad}/{len(catalog)} valid "
          f"against tool-manifest.v1.json\n")

    # 2) run discovery on a real task
    query = "find purchase orders over a threshold that are past due for a supplier"
    resp = search_tools(query, catalog, k=5)

    # 3) validate the search response against the schema
    resp_errs = validate(resp, response_schema)
    print(f"Search response validation against tool-search-response.v1.json: "
          f"{'OK' if not resp_errs else resp_errs}\n")

    print(f"Query: {query!r}")
    print(f"Surfaced {resp['returned']} of {resp['catalog_size']} tools:")
    for r in resp["results"]:
        print(f"  - {r['name']:<26} score={r['score']:.0f}")

    # 4) the PDS payoff: context reduction
    full = sum(_tokens_estimate(m) for m in catalog)
    surfaced = _tokens_estimate(resp)
    reduction = full / max(surfaced, 1)
    print(f"\nContext cost if the whole catalog were dumped in: ~{full:,} tokens")
    print(f"Context cost of the search response actually sent: ~{surfaced:,} tokens")
    print(f"Reduction: ~{reduction:.0f}x  (this is the entire point of PDS)")

    return 0 if bad == 0 and not resp_errs else 1


if __name__ == "__main__":
    sys.exit(main())

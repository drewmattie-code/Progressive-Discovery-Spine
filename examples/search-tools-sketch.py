"""
Progressive Discovery Spine — search_tools implementation sketch
================================================================

Minimal reference of how the `search_tools` entry point works. Demonstrates
principle #3 (tool search as default entry point) in concrete code.

Not production code. No connection handling, no retry, no observability. The
point is to show the *shape* of the retrieval pattern; the gateway and cache
layers live elsewhere.

Stack assumed:
    - PostgreSQL with pgvector for the embedding index
    - Any embedding model (OpenAI, Cohere, local) reachable via `embed()`
    - Tool manifests stored as JSON rows in `tools` table

License: MIT
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolDefinition:
    """One row out of the tool index — what the agent receives."""
    name: str
    description: str
    parameters: dict[str, Any]
    sla: dict[str, Any]
    failure_modes: list[str]


def embed(text: str) -> list[float]:
    """Stub. Real implementation calls your embedding model."""
    raise NotImplementedError("Wire in your embedding model here.")


def search_tools(
    query: str,
    tenant_id: str,
    limit: int = 5,
    db=None,
) -> list[ToolDefinition]:
    """
    The single entry point an agent calls to discover tools.

    Args:
        query:     Natural-language description of what the agent wants to do.
        tenant_id: Active tenant. Used to scope the tool catalog (principle #7).
        limit:     How many tools to return. 5 is a sane default.
        db:        Your database handle (psycopg connection, etc.).

    Returns:
        A list of ToolDefinition objects ranked by relevance. The agent then
        invokes one or more of them through the gateway.

    Notes:
        - Only tools enabled for this tenant are eligible (tenant-scoped catalog).
        - The `intent_examples` field in each tool manifest is embedded along
          with the description, so phrasings like "show me open POs for X"
          match `search_open_pos` even though "show me" doesn't appear in the
          formal description.
        - Re-embed the index on every tool release.
    """
    query_vec = embed(query)

    rows = db.execute(
        """
        SELECT
            name,
            description,
            parameters,
            sla,
            failure_modes,
            embedding <=> %s AS distance
        FROM tools
        WHERE tenant_id = %s
          AND enabled = TRUE
        ORDER BY distance ASC
        LIMIT %s
        """,
        (query_vec, tenant_id, limit),
    ).fetchall()

    return [
        ToolDefinition(
            name=r["name"],
            description=r["description"],
            parameters=r["parameters"],
            sla=r["sla"],
            failure_modes=r["failure_modes"],
        )
        for r in rows
    ]


# -----------------------------------------------------------------------------
# Example of how an agent uses it
# -----------------------------------------------------------------------------

def agent_loop_example():
    """
    Pseudo-code showing the contract from the agent's side. The agent's
    permanent toolbelt is just `search_tools`. Everything else is discovered.
    """

    # Step 1: agent gets a task.
    task = "I need to know which customers are exposed to Eaton lead-time risk"

    # Step 2: agent asks PDS what tools could help.
    tools = search_tools(
        query="customer exposure to a supplier's lead-time risk",
        tenant_id="acme-corp",
        limit=5,
    )

    # Step 3: agent reads the tool descriptions + SLAs and picks the right one(s).
    # The model can read SLA metadata and route around degradation — for example,
    # if `p95_latency_ms > 5000` for a tool, pick the cached-CDC alternative.

    # Step 4: agent calls the chosen tool through the gateway (not shown).
    # Gateway handles retry / backpressure / observability / audit.

    return tools


# -----------------------------------------------------------------------------
# Notes on the index
# -----------------------------------------------------------------------------
#
# The `tools` table schema looks roughly like:
#
#   CREATE TABLE tools (
#       id              BIGSERIAL PRIMARY KEY,
#       tenant_id       TEXT NOT NULL,
#       name            TEXT NOT NULL,
#       version         TEXT NOT NULL,
#       description     TEXT NOT NULL,
#       intent_examples TEXT[] NOT NULL,
#       parameters      JSONB NOT NULL,
#       sla             JSONB NOT NULL,
#       failure_modes   TEXT[] NOT NULL,
#       enabled         BOOLEAN NOT NULL DEFAULT TRUE,
#       embedding       VECTOR(1536) NOT NULL,
#       updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
#       UNIQUE(tenant_id, name, version)
#   );
#
#   CREATE INDEX tools_embedding_idx
#     ON tools USING ivfflat (embedding vector_cosine_ops);
#
# The embedding is computed over the concatenation of:
#   - description
#   - intent_examples (joined with newlines)
#   - the tool's parameter names (so "supplier" / "date_range" appear in the
#     embedded text and lexical-ish queries find the right tool)
#
# Re-embed on every tool publish. Versioning lets you keep the old embedding
# active until the new one is indexed.

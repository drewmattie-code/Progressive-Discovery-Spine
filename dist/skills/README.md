# PDS Claude skills

This directory holds the PDS architectural-consultant skill in a format that drops directly into Claude Code, Codex, Cursor, and other clients that support the skills convention.

## Install for Claude Code

```bash
mkdir -p ~/.claude/skills/pds
cp pds/SKILL.md ~/.claude/skills/pds/SKILL.md
```

Restart your Claude Code session (or run `/help` and confirm the skill appears).

The skill will then activate automatically when you ask architectural questions about MCP at scale, agent-to-enterprise integration, tool-catalog management, or any of the other triggering contexts described in the SKILL frontmatter.

## What the skill does

It's an architectural consultant, not a code library. When triggered, Claude (or another supporting agent) will:

1. Diagnose which of the four documented MCP-at-scale failure modes you're hitting (context bloat, hallucinated tool selection, production gaps, discovery anti-patterns)
2. Recommend the 2–3 PDS principles that address it
3. Give one concrete next step
4. Link to the full spec for deeper reading

It will NOT install software, pretend to be a runnable library, or recite the whole spec at you. The point is fast diagnosis.

## Other clients

The SKILL.md format is portable. Drop it into:

- **Cursor** — `~/.cursor/skills/pds/SKILL.md`
- **Codex** — `~/.codex/skills/pds/SKILL.md`
- Any other agent that supports the SKILL.md / agent-skill convention

For agents that don't natively support the skills convention, the SKILL.md is also readable as a prompt — paste it into a system prompt or context.

## Versioning

The skill version tracks the spec version. Current: v1.0 (matches SPEC.md v1.0).

When the spec evolves, the skill evolves with it. Watch this repo (or the [CHANGELOG](../../README.md) once we ship one) for updates.

## Attribution

Progressive Discovery Spine by Drew Mattie · SaaSquach AI Labs (a division of Charles & Roe Inc.) · CC BY 4.0

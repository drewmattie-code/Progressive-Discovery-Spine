# Contributing to PDS

Thanks for your interest in the Progressive Discovery Spine specification.

PDS is a **pattern specification**, not a software library. Contributions are most useful in three forms:

## 1. Implementation reports

If you have built a system that implements PDS (or pieces of it) in production, an issue or PR describing what worked, what didn't, and what you'd refine is the highest-value contribution. Anonymized is fine, patterns and surprises matter more than vendor names.

Template: open an issue with title `[Implementation] <one-line summary>` and include:

- Stack (backend systems, agent framework, MCP servers, deployment shape)
- Which of the 10 principles you implemented and which you skipped, and why
- What broke and how you fixed it
- What SLAs you measured against the targets in [SPEC.md](SPEC.md#4-slas-and-success-metrics)

## 2. Pattern refinements and additions

If you find a missing principle, an unhandled failure mode, or a refinement to an existing principle, open an issue first to discuss before sending a PR. The spec is intentionally tight, every principle has earned its place. New principles need to be load-bearing, not nice-to-have.

Refinements to existing principles are easier: open a PR with the proposed change to [SPEC.md](SPEC.md) and a one-paragraph rationale. Cite implementations or production incidents where possible.

## 3. Examples and reference materials

The [`examples/`](examples/) directory is open to:

- More worked tool manifests for additional domains (CRM, finance, healthcare, manufacturing)
- Implementation sketches in additional languages (the current one is Python)
- Action-menu UI patterns
- Gateway configuration examples

Keep examples small and concrete. The point is to show the shape; production-grade implementations belong in your own repo.

## What we won't accept

- Vendor advertising: examples that exist primarily to promote a product. Keep examples vendor-neutral; if you need to name a backend, use it as one of many examples.
- Speculative principles: additions without an implementation that supports them.
- Cosmetic edits without rationale.

## Style

- Prose: declarative, no fluff. Match the existing voice in [SPEC.md](SPEC.md).
- Diagrams: Mermaid where possible (renders natively in GitHub).
- Code samples: minimal, runnable, no external dependencies beyond `requirements.txt` / `package.json` declarations.
- Markdown: GitHub-flavored. Wrap at natural sentence boundaries, not at fixed columns.

## License agreement

Contributions are accepted under the project's dual license (CC BY 4.0 for prose, MIT for code). By opening a PR, you agree to license your contribution under those terms.

## Reporting issues with the spec

If you think a principle is wrong, please say so directly in an issue. Include the principle number, what's wrong, and what you'd change. The spec is not gospel; it's the current best understanding.

## Contact

Open an issue for anything spec-related. For something that doesn't fit an issue, the author's contact is in the repository About section.

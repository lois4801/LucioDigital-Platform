# LucioDigital Phase 12 — Persistent Project Intelligence

## Purpose

Phase 12 gives LucioDigital Dev Agent durable, app-scoped project memory so future coding sessions can use prior architecture, verified capabilities, known failures, and explicit human decisions instead of starting from zero.

## Data model

MongoDB collections:

- `dev_agent_project_intelligence` — one bounded project snapshot per LucioDigital app
- `dev_agent_project_decisions` — explicit human architecture/product/security/deployment decisions

The snapshot is derived from existing LucioDigital app metadata and Dev Agent sessions. It does not store credentials, environment variables, raw private transcripts, or runner secrets.

## Memory supplied to Dev Agent

Before planning and coding, Lucio injects a compact `project_memory` object containing:

- project identity and Dev Agent repository/scaffold configuration
- the most recent architecture/repository inspection
- verified capabilities from evidence-backed runs
- explicit human project decisions
- recent successful runs
- recent known failures

The memory payload is hard bounded before it is inserted into an LLM prompt.

## UI

The Dev Agent tab now includes a Project Intelligence panel with:

- run/verification/browser-QA/approval/publication statistics
- architecture snapshot and remembered files
- verified capability badges
- known failure history
- recent remembered runs
- human decision editor
- manual refresh control

## Runtime integration repair

During Phase 12 verification we found that Dev Agent modules existed in the repository but were not mounted in the visible FastAPI registration block. The `access.register(...)` bootstrap now registers, in order:

1. Project Intelligence and memory hooks
2. Core Dev Agent routes
3. GitHub publishing routes
4. Railway deployment-control routes
5. Browser QA and bounded browser self-healing routes

This restores the intended Dev Agent API surface without rewriting the large `server.py` registration section.

## Safety

- memory is scoped by `app_id`
- access follows existing owner/member authorization
- only owner/admin/editor roles may add or delete project decisions
- no secrets are persisted in project intelligence
- memory never grants new execution permissions
- deployment, GitHub publishing and production promotion remain separately gated

## Verification requirements

Before merge:

- Python compilation for Project Intelligence and all Dev Agent runtime modules
- import smoke test for `project_intelligence`
- full frontend production build

After merge:

- Railway backend deploy succeeds
- `/health` returns 200
- Dev Agent API paths are present in the live FastAPI application
- Railway frontend deploy succeeds
- Project Intelligence panel is available under the Dev Agent tab

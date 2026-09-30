# Lucio Dev Agent — Goal → Working App

This document describes the first production implementation of Lucio's agentic development system.

## Phase 1 — Dev Agent MVP

Implemented in `backend/dev_agent.py` and `frontend/src/components/DevAgentPanel.tsx`.

Capabilities:
- connect a Lucio project to a GitHub repository and branch;
- inspect repository files and detected stack through Nexus Runner;
- turn a natural-language goal into an ordered implementation plan;
- maintain durable development sessions in MongoDB;
- read/search code, write new files, perform exact text replacements, and run constrained commands;
- show a chronological tool/action timeline in the Lucio UI;
- show Git diffs and untracked files before approval.

## Phase 2 — Isolated Runtime + Live Preview

Implemented in the separate `runner/` service.

The production Lucio API never runs generated code. Nexus Runner is deployed as a separate Railway service with no production database credentials. It clones one repository per Dev Agent session under an ephemeral workspace root and exposes only an authenticated tool API.

Current runtime controls:
- repository URLs are restricted to HTTPS GitHub URLs without embedded credentials;
- all file paths are contained inside the session workspace;
- `.env`, `.git`, SSH keys, cloud credential paths and other secret-like files are denied to agent tools;
- shell execution is disabled; commands use argument arrays and a binary allow-list;
- command output, file reads/writes and execution time are bounded;
- preview processes run in the runner service rather than in the production backend;
- human approval remains separate from execution.

For a public multi-tenant product, the next hardening step is one container/microVM per active workspace. The current runner isolates generated code from Lucio production but multiple development workspaces can still share the same runner container.

## Phase 3 — Agentic Orchestration + Self-Healing

Implemented in `backend/dev_agent.py`.

Flow:

`Goal → Inspect → Plan → Tool loop → Verify → Repair loop → Diff → Review → Preview → Human approval`

The planning result assigns tasks to conceptual specialist roles (frontend, backend, database, QA, DevOps and reviewer). The coding executor then works one tool action at a time and is required to read relevant code before changing it.

If automated verification fails, Lucio performs a bounded repair pass using the exact failure evidence and re-runs verification. The final reviewer receives the requested goal, change set and verification evidence and produces a separate review record.

## Phase 4 — Goal → Working App Experience

The Dev Agent is surfaced as a first-class tab inside every Lucio project. The UI includes:
- GitHub project connection;
- natural-language build goal;
- **Create plan** and **Plan & build** actions;
- live run status and agent timeline;
- test/build results;
- change-set review;
- live sandbox preview when a preview command is available;
- follow-up instructions using the same workspace;
- approve/reject gates.

This implementation is intentionally repository-first. New-project-from-zero scaffolding and automatic GitHub branch publishing/deployment are the next extensions after the execution path is proven in production.

## Railway services

Recommended service layout:

- `lucio-frontend` — public UI;
- `lucio-backend` — public FastAPI application API;
- `mongo` — private database only;
- `nexus-runner` — isolated code execution / preview service.

Required environment variables:

### `lucio-backend`

- `NEXUS_RUNNER_URL` — Nexus Runner service URL;
- `NEXUS_RUNNER_SECRET` — high-entropy shared service credential;
- existing LLM provider configuration used by `llm_provider.py`.

### `nexus-runner`

- `NEXUS_RUNNER_SECRET` — same shared credential;
- `NEXUS_RUNNER_PUBLIC_URL` — public runner URL used to construct sandbox preview URLs;
- `WORKSPACE_ROOT=/tmp/lucio-workspaces`;
- `PORT` supplied by Railway.

Never put the runner credential, provider API keys, GitHub tokens or production database credentials in repository source.

## Approval boundary

Dev Agent may automatically inspect, edit, build and test **inside the runner workspace**. Human approval is required before accepted changes are treated as final. Production deployment, database migrations, domain changes, authentication changes and secret changes should remain separately gated even after Git publishing is added.

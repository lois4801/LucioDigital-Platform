# Lucio Dev Agent — Phase 6: Approval-Gated GitHub Publishing

## Purpose

Phase 6 turns an approved Lucio Dev Agent run into a reviewable GitHub branch without allowing generated code to write directly to production or the repository base branch.

## Safety boundary

The execution runtime and GitHub publishing credentials stay separated:

1. Nexus Runner clones/scaffolds, edits, tests and previews code in an isolated workspace.
2. Lucio backend stores the approved source as a durable ZIP artifact.
3. A human approves the change set.
4. The Lucio backend — never Nexus Runner — uses the configured GitHub credential.
5. Lucio creates a new branch from the configured base branch and writes only the approved changed files/deletions.
6. Lucio never auto-merges the branch.
7. The user receives GitHub branch, commit and compare/PR URLs for review.

## Routes

- `GET /api/dev-agent/publishing` — reports whether backend GitHub publishing is connected.
- `GET /api/apps/{app_id}/dev-agent/sessions/{session_id}/publish-readiness` — explains whether an approved run is ready to publish.
- `POST /api/apps/{app_id}/dev-agent/sessions/{session_id}/publish` — publishes the approved artifact to a new GitHub branch.

## Required conditions

Publishing is permitted only when all of the following are true:

- the Dev Agent session is `approved`;
- automated verification passed;
- the session originated from an existing GitHub repository;
- the durable approved ZIP artifact exists;
- the backend GitHub publishing credential is configured;
- the target repository owner is allowed when an owner allow-list is configured;
- the requested publish branch is different from the base branch and does not already exist.

## Backend configuration

For the current single-owner/admin MVP, the backend accepts:

- `LUCIO_GITHUB_TOKEN` — GitHub credential stored only in the backend environment/secrets store;
- `LUCIO_GITHUB_ALLOWED_OWNER` — optional owner allow-list, recommended for the current deployment;
- `DEV_AGENT_PUBLISH_MAX_FILES` — optional publish file limit;
- `DEV_AGENT_PUBLISH_MAX_BYTES` — optional source-byte limit.

Do not place these values in source control, frontend variables, Nexus Runner variables, generated applications or repository URLs.

## Multi-tenant production requirement

Before unrelated customers can publish to their own GitHub accounts, replace the single backend credential with a GitHub App or OAuth connection per user/workspace. Tokens must remain server-side and scoped to the minimum repository permissions required.

## Current scaffold behavior

Runs created from Lucio's built-in React/FastAPI scaffolds can be approved and downloaded as durable ZIP artifacts. Creating a brand-new GitHub repository automatically is intentionally not part of this phase; it requires a separate explicit GitHub account authorization and repository-creation workflow.

## Future deployment gate

GitHub publishing is not production deployment. A later deployment phase should require a separate explicit approval, then deploy the reviewed branch/commit to a preview environment before any production promotion.

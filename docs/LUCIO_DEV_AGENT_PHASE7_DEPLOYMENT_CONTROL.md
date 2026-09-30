# Lucio Dev Agent — Phase 7: Preview Deployment Control Plane

## Goal

Phase 7 adds a safe promotion path after code generation. A reviewed change is not automatically production code.

The enforced lifecycle is:

`Build → Verify → Human Approve → Publish GitHub Branch → Preview Deploy → Preview Verify → Production Request`

Production deployment itself remains disabled in this phase.

## Railway preview provider

Lucio uses Railway's documented GraphQL Public API at `https://backboard.railway.com/graphql/v2`.

Preferred authentication is a **project token**, scoped to the target Railway environment. It is sent with the `Project-Access-Token` header. Account/workspace/OAuth bearer credentials are supported for future integrations but have broader scope.

### Backend-only variables

- `LUCIO_RAILWAY_PROJECT_TOKEN` — preferred project-scoped credential
- `LUCIO_RAILWAY_TOKEN` — optional bearer credential alternative
- `LUCIO_RAILWAY_PROJECT_ID` — destination Railway project
- `LUCIO_RAILWAY_ENVIRONMENT_ID` — destination preview environment
- `LUCIO_RAILWAY_PREVIEW_ENABLED=true` — explicit kill-switch/enable flag

These values must never be exposed to the frontend, Nexus Runner, generated code, GitHub branches, logs, or user prompts.

## Safety gates

A preview is created only when:

1. the Dev Agent run is human-approved;
2. automated verification passed;
3. the approved code was published to a reviewable GitHub branch;
4. Railway preview deployment is explicitly configured and enabled;
5. no preview service already exists for the session.

Preview creation is idempotent at the Dev Agent session level. Repeated calls return the existing preview record instead of creating additional services.

## Railway actions

The backend uses the documented API to:

- create a service from the published GitHub repository and branch;
- request a deployment;
- create a Railway-provided preview domain;
- query deployment status and preview domain state.

The Railway credential stays in the Lucio backend only.

## API routes

- `GET /api/dev-agent/deployment-control`
- `GET /api/apps/{app_id}/dev-agent/sessions/{session_id}/preview-readiness`
- `POST /api/apps/{app_id}/dev-agent/sessions/{session_id}/preview-deploy`
- `POST /api/apps/{app_id}/dev-agent/sessions/{session_id}/preview-refresh`
- `POST /api/apps/{app_id}/dev-agent/sessions/{session_id}/production-request`

## Production gate

`production-request` records intent only. It performs no production deployment. A later production-promotion phase must require a second explicit approval, pin the reviewed commit SHA, perform production health checks, and support rollback.

## Cost / lifecycle note

A Railway preview service consumes Railway resources. Lucio therefore creates at most one preview service per Dev Agent session. Automated preview cleanup/TTL is a later lifecycle feature and should be added before enabling large-scale multi-tenant preview creation.

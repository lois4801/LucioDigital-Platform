# LucioDigital Phase 13 — AI Command Center

## Goal
Make LucioDigital's LLM and Dev Agent capabilities visible and usable from the main Agency Workspace instead of requiring users to discover them inside an individual project.

## Dashboard command center
The dashboard now surfaces:
- LLM runtime state
- Nexus Runner state
- persistent project-memory state
- Chromium Browser QA state
- GitHub publishing readiness
- Railway preview-deployment readiness
- platform model selector
- existing-project selector
- one-prompt Dev Agent launch
- direct link into the selected project's Dev Agent workspace
- visible Planner, Coding Agent, QA, Browser QA, Reviewer and Deployment roles

## Backend cleanup
`access.register(...)` is the single Dev Agent runtime bootstrap. `ai_models.register(...)` no longer registers Dev Agent, GitHub publishing, Railway deployment control or Browser QA a second time.

The platform model update endpoint now authorizes LucioDigital owners through the same owner allowlist used by the rest of the platform.

`/api/ai/models` returns runtime readiness as booleans only. Secret values are never returned.

## BYO providers
The existing `emergentintegrations==0.2.0` package supplies the compatible LiteLLM runtime used by the current provider layer. Do not add a second exact LiteLLM version pin beside it: Railway's dependency resolver correctly rejects conflicting exact LiteLLM requirements.

A future provider-decoupling phase can remove the Emergent integration dependency entirely and then pin/manage LiteLLM (or direct provider SDKs) independently.

Provider credentials still remain server-side environment variables. The dashboard only displays whether a provider/runtime is available.

## Safety
- no API keys are exposed to the frontend
- generated code still executes only inside Nexus Runner
- GitHub branch publishing remains approval-gated
- Railway preview deployment remains separately gated
- production promotion remains a separate operation
- this phase does not enable provider credentials or create paid resources by itself

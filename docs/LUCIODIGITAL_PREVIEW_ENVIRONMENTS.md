# LucioDigital Preview Environments

## Purpose

Every substantive LucioDigital change should be testable in an isolated live preview before it is merged to `main` and promoted to production.

This policy applies only to **LucioDigital** (`lois4801/LucioDigital-Platform`). It does not apply to the separate Lucio AI Platform product/repository.

## Required delivery flow

1. Create a feature branch.
2. Implement the change on that branch.
3. Open a pull request to `main`.
4. Run the `LucioDigital Preview Readiness` workflow.
5. Railway creates a PR Environment for the pull request.
6. Verify backend, frontend, Nexus Runner, live preview, Browser QA, and any feature-specific acceptance checks.
7. Share the Railway live preview URL for user testing.
8. Fix issues on the same feature branch and retest the updated preview.
9. Merge only after preview verification and approval.
10. Verify the production Railway deployment after merge.
11. Share the final production URL.

## Railway configuration

Railway PR Environments are enabled once in the Railway dashboard:

- Project: `LucioDigital Data (Old)`
- Project ID: `77f034d1-e0c5-42dc-9e38-7e324e238dd6`
- Project Settings → Environments → Enable PR Environments
- Prefer a dedicated `staging` base environment rather than production.
- Enable Focused PR Environments when appropriate for this monorepo so unchanged services do not rebuild unnecessarily.

A PR Environment is ephemeral and should be removed automatically by Railway when its pull request is merged or closed.

## Isolation rules

Preview environments must not depend on or mutate production data.

- Use a preview/staging MongoDB database or Railway database instance.
- Never point preview code to the production `luciodigital` database.
- Use test-only credentials for integrations.
- Disable or stub outbound email, SMS, WhatsApp, billing, webhooks, destructive jobs, and other real-world side effects unless a dedicated sandbox provider is configured.
- Do not copy production-only sealed secrets into preview environments.
- Nexus Runner credentials remain server-to-server only.
- GitHub and Railway write credentials must never be exposed to generated applications or browser code.

## Production gate

A successful CI build is not sufficient for production promotion. The expected gate is:

`feature branch → CI → Railway PR Environment → live testing → Browser QA → approval → merge → production health verification`

## Definition of done

A LucioDigital update is complete only when:

- source changes are committed to GitHub;
- CI passes;
- a live preview is available and tested when the change affects runtime behavior;
- the approved change is merged to `main`;
- Railway production deployment is healthy; and
- the final production link is supplied for verification.

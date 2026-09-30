# Lucio Dev Agent — Phase 9: Browser QA Evidence

## Goal

Phase 8 gave Nexus Runner a real Chromium QA engine. Phase 9 connects that engine back to Lucio so browser verification becomes part of a Dev Agent session instead of an isolated runtime capability.

## Flow

1. Dev Agent creates/edits code in Nexus Runner.
2. Normal code verification passes.
3. The workspace preview is running.
4. Lucio requests Browser QA for a selected preview route.
5. Nexus Runner opens the route in Chromium and returns structured runtime evidence.
6. Lucio stores that evidence on the Dev Agent session and adds a pass/fail event to the agent timeline.
7. Optional screenshot bytes are persisted through Lucio's configured storage backend (GridFS in the current Railway deployment).

## Stored evidence

A session may contain `browser_qa` with:

- pass/fail status;
- HTTP response status;
- title and rendered body text;
- rendered HTML size;
- interactive element count;
- missing expected text;
- console errors;
- page JavaScript errors;
- failed requests;
- viewport;
- optional persisted screenshot URL;
- check timestamp and requesting user.

## API

- `GET /api/dev-agent/browser-qa` — checks whether the Browser QA runtime is reachable through Nexus Runner.
- `POST /api/apps/{app_id}/dev-agent/sessions/{session_id}/browser-qa` — runs Chromium QA against the active workspace preview and stores evidence.
- `GET /api/apps/{app_id}/dev-agent/sessions/{session_id}/browser-qa` — reads stored evidence.

## Security

- The frontend never receives `NEXUS_RUNNER_SECRET`.
- Lucio backend performs the authenticated service-to-service request.
- Browser QA targets only the workspace-local preview in Nexus Runner.
- Screenshot bytes are bounded before storage.
- No Railway, GitHub, Mongo or model-provider credential is sent to Chromium.

## Next phase

Phase 10 should make Browser QA part of the bounded self-healing loop: when Browser QA fails, the agent receives a concise evidence packet, performs a limited repair pass, reruns code verification, restarts/refreshes the preview and reruns Browser QA before human approval.

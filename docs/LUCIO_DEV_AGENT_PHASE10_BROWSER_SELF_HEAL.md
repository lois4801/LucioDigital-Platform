# Lucio Dev Agent — Phase 10: Browser QA Self-Healing

## Purpose

Phase 10 turns Chromium runtime evidence into a bounded coding-repair loop. It is designed to fix demonstrated browser/runtime failures without creating an unlimited autonomous loop.

## Flow

1. A Dev Agent workspace has a running preview.
2. Lucio runs Chromium Browser QA.
3. If Browser QA passes, the run is recorded as browser-verified and no repair occurs.
4. If Browser QA fails, Lucio compacts the browser evidence into a repair packet.
5. The existing Dev Agent coding model receives that evidence and may perform up to the configured bounded number of safe tool actions.
6. Normal project verification is rerun.
7. If normal verification passes, Chromium Browser QA is rerun.
8. The final verification, browser evidence and Git diff are saved back to the session.

## Browser evidence used for repair

- HTTP response status
- missing expected text
- browser console errors
- JavaScript page errors
- failed requests
- body-text excerpt
- viewport

The model is instructed to fix only the demonstrated runtime issue(s), preserve working behavior and never invent success.

## Safety bounds

- repair uses the existing Nexus Runner tool allow-list;
- no arbitrary shell operators or secret paths are added;
- each request allows at most 8 repair actions;
- each Dev Agent session allows at most 2 browser repair attempts;
- a running Dev Agent execution cannot be repaired concurrently;
- normal build/test verification must pass after the repair;
- Chromium must pass again before the repair is considered successful;
- production remains untouched.

## API

`POST /api/apps/{app_id}/dev-agent/sessions/{session_id}/browser-self-heal`

The request can specify:

- preview path;
- expected visible text;
- viewport dimensions;
- whether console errors fail QA;
- bounded repair-step count.

## Approval model

A successful self-heal updates the session change set and verification evidence. It does not automatically approve, publish, merge or deploy the changes. Human approval remains a separate gate.

# Lucio Dev Agent — Phase 8: Browser QA Runtime

## Goal

Phase 8 adds a real Chromium verification layer to Nexus Runner. Compilation and unit tests are not enough to prove that an app actually renders or behaves correctly in a browser.

The browser QA runtime operates only against an already-running isolated workspace preview.

## What it checks

For a requested preview path, Chromium records:

- top-level HTTP response status;
- document title and visible body text;
- page JavaScript errors;
- browser console errors;
- failed network requests;
- expected text assertions;
- interactive element count;
- rendered HTML size;
- optional bounded viewport screenshot evidence.

The result contains a single `ok` value plus structured evidence that can be fed back into the Dev Agent repair loop.

## Security boundary

Browser QA runs inside Nexus Runner, not the Lucio production backend.

- It can navigate only the local preview URL for the requested workspace.
- It does not accept arbitrary external URLs.
- The runner bearer credential is captured at service startup and removed from the process environment before generated code, preview commands or Chromium are launched.
- Browser QA does not receive Lucio database credentials, Railway tokens, GitHub tokens or provider API keys.
- Chromium launches headless with `--no-sandbox` and `--disable-dev-shm-usage` inside the isolated runner container.

## Runner API

- `GET /v1/browser-qa/status`
- `POST /v1/workspaces/{workspace_id}/browser-qa`

Example request fields:

- `path`: preview route such as `/` or `/dashboard`;
- `expected_text`: strings that must appear in the rendered page;
- `viewport_width` / `viewport_height`;
- `screenshot`: whether to return bounded PNG evidence;
- `fail_on_console_errors`: whether console errors fail QA.

## Next integration step

The next Dev Agent integration phase should call Browser QA after a successful code/build verification and live preview, then:

1. mark the run browser-verified when QA passes;
2. feed console/page/network evidence back into the repair model when QA fails;
3. rerun code verification and Browser QA after a bounded repair attempt;
4. expose the browser QA evidence in the Lucio Dev Agent timeline and approval panel.

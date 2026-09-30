"""Browser QA extension for Nexus Runner.

Runs real Chromium against the already-running local workspace preview. It does not need or
receive Lucio production credentials. Results are bounded and structured so the Dev Agent can
use them as repair evidence.
"""
from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright

import server


class BrowserQARequest(BaseModel):
    path: str = "/"
    wait_ms: int = Field(default=500, ge=0, le=5000)
    timeout_ms: int = Field(default=20000, ge=2000, le=60000)
    viewport_width: int = Field(default=1440, ge=320, le=2560)
    viewport_height: int = Field(default=900, ge=320, le=2000)
    expected_text: List[str] = Field(default_factory=list, max_length=20)
    screenshot: bool = False
    fail_on_console_errors: bool = True


def _preview_target(workspace_id: str, path: str) -> str:
    meta = server.PREVIEWS.get(workspace_id)
    if not meta:
        raise HTTPException(409, "Start the workspace preview before running browser QA")
    process = meta.get("process")
    if not process or process.poll() is not None:
        info = server._preview_info(workspace_id) or {}
        raise HTTPException(409, f"Workspace preview is not running: {(info.get('logs') or '')[-800:]}")
    clean_path = "/" + (path or "/").lstrip("/")
    return f"http://127.0.0.1:{int(meta['port'])}{clean_path}"


def register(app):
    @app.get("/v1/browser-qa/status", dependencies=[Depends(server._auth)])
    async def browser_qa_status():
        return {
            "available": True,
            "engine": "chromium",
            "scope": "workspace-preview-only",
            "screenshots": True,
        }

    @app.post("/v1/workspaces/{workspace_id}/browser-qa", dependencies=[Depends(server._auth)])
    async def browser_qa(workspace_id: str, body: BrowserQARequest):
        # Validate that this is a real runner workspace even though Chromium only consumes the preview.
        server._workspace(workspace_id)
        target = _preview_target(workspace_id, body.path)

        console_errors: List[str] = []
        page_errors: List[str] = []
        failed_requests: List[Dict[str, str]] = []
        response_status: Optional[int] = None
        screenshot_b64: Optional[str] = None

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            context = await browser.new_context(
                viewport={"width": body.viewport_width, "height": body.viewport_height},
                ignore_https_errors=False,
            )
            page = await context.new_page()

            def on_console(msg):
                if msg.type == "error" and len(console_errors) < 40:
                    console_errors.append(msg.text[:1200])

            def on_page_error(exc):
                if len(page_errors) < 20:
                    page_errors.append(str(exc)[:1600])

            def on_request_failed(req):
                if len(failed_requests) < 40:
                    failure = req.failure
                    failed_requests.append({
                        "url": req.url[:1200],
                        "method": req.method,
                        "error": str(failure or "request failed")[:500],
                    })

            page.on("console", on_console)
            page.on("pageerror", on_page_error)
            page.on("requestfailed", on_request_failed)

            try:
                response = await page.goto(target, wait_until="networkidle", timeout=body.timeout_ms)
                response_status = response.status if response else None
                if body.wait_ms:
                    await page.wait_for_timeout(body.wait_ms)
                title = (await page.title())[:500]
                body_text = (await page.locator("body").inner_text(timeout=5000))[:12000]
                html_size = len((await page.content()).encode("utf-8"))
                interactive_count = await page.locator("a,button,input,select,textarea,[role=button]").count()
                missing_text = [text for text in body.expected_text if text and text.lower() not in body_text.lower()]
                if body.screenshot:
                    shot = await page.screenshot(type="png", full_page=False)
                    # Keep response size bounded. The UI/agent can request a screenshot only when useful.
                    if len(shot) <= 2_000_000:
                        screenshot_b64 = base64.b64encode(shot).decode("ascii")
            except Exception as exc:
                await browser.close()
                return {
                    "ok": False,
                    "url": target,
                    "status": response_status,
                    "title": "",
                    "body_text": "",
                    "html_bytes": 0,
                    "interactive_elements": 0,
                    "missing_text": list(body.expected_text),
                    "console_errors": console_errors,
                    "page_errors": [*page_errors, str(exc)[:1600]][:20],
                    "failed_requests": failed_requests,
                    "screenshot_base64": None,
                    "viewport": {"width": body.viewport_width, "height": body.viewport_height},
                }
            finally:
                if browser.is_connected():
                    await browser.close()

        http_ok = response_status is None or response_status < 400
        runtime_ok = not page_errors and not failed_requests
        console_ok = not console_errors if body.fail_on_console_errors else True
        content_ok = not missing_text
        return {
            "ok": bool(http_ok and runtime_ok and console_ok and content_ok),
            "url": target,
            "status": response_status,
            "title": title,
            "body_text": body_text,
            "html_bytes": html_size,
            "interactive_elements": interactive_count,
            "missing_text": missing_text,
            "console_errors": console_errors,
            "page_errors": page_errors,
            "failed_requests": failed_requests,
            "screenshot_base64": screenshot_b64,
            "viewport": {"width": body.viewport_width, "height": body.viewport_height},
        }

    return {"registered": True, "engine": "chromium"}

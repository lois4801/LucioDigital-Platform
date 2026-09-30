"""Boot Nexus Runner while keeping service credentials out of child-process environments.

`server` captures the required service settings at import time. Browser QA registers its routes
against the same FastAPI app, then service credentials are removed from `os.environ` before
uvicorn begins serving requests. Any later build, test, preview or Chromium process launched by
the runner therefore cannot inherit the runner bearer credential.
"""
import os

import uvicorn

import server
import browser_qa

browser_qa.register(server.app)

# `server.RUNNER_SECRET` and `server.RUNNER_PUBLIC_URL` already hold these values in memory.
# Generated/build/browser code must never inherit service-to-service credentials.
os.environ.pop("NEXUS_RUNNER_SECRET", None)
os.environ.pop("NEXUS_RUNNER_PUBLIC_URL", None)
os.environ.pop("NEXUS_RUNNER_ALLOW_INSECURE", None)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "9000"))
    uvicorn.run(server.app, host="0.0.0.0", port=port)

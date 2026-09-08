# Lois-Tech — Product Requirements & Status

## Problem statement
Production-ready multi-tenant SaaS application builder merging Framer-style visual website building
(Site Mode) with Lovable-style conversational AI app generation (App Mode).

Core requirements:
1. Global dashboard with dual modes (Site Mode canvas / App Mode chat)
2. 16 pre-built industry templates with fixed layouts
3. High-end UI/UX with premium animations
4. AI-scored Lead Inbox with inline AI draft replies + auto-classification (real vs test)
5. Export & Handoff pipeline: Website, Full-Stack App, Plugin package (+ plugin zip re-import)
6. Admin-editable CMS for the public landing page with dynamic Showcase manager (stars + drag-to-reorder)
7. Tenant Overview dashboards that auto-sync with live Site Mode edits
8. Static site → full-stack web app conversion (auth, db, CMS)
9. Booking calendar, paid members area, client panel

## Architecture
React (Vite/craco) + Tailwind + Shadcn UI · FastAPI (port 8001, all routes under /api) · MongoDB.
Auth is **cookie-based** JWT (HttpOnly, SameSite=None) — login returns the user object, not a token.
Backend modules: server.py, site_content.py, site_sync.py, content_lock.py, locks.py, inbox.py,
lead_class.py, export_pkg.py, export_gen.py, landing_cms.py, ai_models.py, seed_sites.py, storage.py.

## Integrations
- Emergent Universal Key — Claude / GPT / Gemini text + image
- Stripe (env key `sk_test_emergent`) — payments
- Emergent-managed Resend — live email
- Emergent-managed Google Auth

## Implemented (to Sept 8, 2026)
- Full platform: Site Mode canvas, App Mode AI generation, templates, CMS, file library,
  bookings, paid memberships, client portals, locks (master + granular), content lock
- Export pipeline (Website / Full-Stack App / Plugin) + plugin zip re-import
- Lead Inbox with auto-classification (real/test), admin override, AI draft replies,
  AI lead summary, lead source insights, live email delivery, auto-archive cron
- Dynamic landing page showcase + Showcase Manager (featured stars, drag-to-reorder)
- Tenant Overview auto-sync with Site Mode edits
- Rebrand OmniStack → Lois-Tech (UI-wide)
- **Sept 8, 2026 — regression pass (iter 55/56) + fixes:**
  - `seed_sites.ensure_editor_tenant()` idempotently restores canonical tenant
    `app_6663b5de0007` (Northwind Roofing, 4 pages) and re-attaches `client.editor` as editor —
    fixes the editor account seeing zero tenants after a DB wipe. Stable across restarts.
  - `GET /api/public/showcase` is now data-driven (preview_enabled apps) instead of a hardcoded
    name map that returned [].
  - Removed leftover Iter53 throwaway test tenants (7 tenants now).
- **Sept 8, 2026 — deployment blockers fixed (deployment_agent: PASS):**
  - Added unprefixed `GET /health` + `GET /api/health` → the k8s liveness probe was 404ing, which
    was the actual cause of the failed deploy.
  - CORS: `CORS_ORIGINS="*"` with `allow_origin_regex=".*"` in CORSMiddleware, because
    `allow_credentials=True` cannot be paired with a literal `"*"` origin and auth uses cookies.
  - Startup seeding wrapped in try/except and skips gracefully when `ADMIN_EMAIL`/`ADMIN_PASSWORD`
    secrets are absent (previously a `KeyError` crash-looped the container on Atlas).
  - Request-path `os.environ["ADMIN_EMAIL"]` hard lookups → `.get()` in server.py, landing_cms.py,
    ui_cms.py, data_destinations.py.

## Backlog
- **P1** Real ElevenLabs voice — MOCKED; needs the user's ElevenLabs API key (next in the agreed order)
- **P1** External DB sync export target (Supabase / PostgreSQL) + cloud drives
- **P1** Real GitHub push integration — MOCKED; user chose to hold off on providing a PAT
- **P2** Member "Delete my account" flow in profile
- **P2** `is_test` flag on tenants + admin "Archive test tenants" action
- **P2** Legacy suites `test_iter11..52` hardcode dead tenant ids and 404 — refactor to a shared
  dynamic-tenant conftest fixture or delete
- **P3** Internal `omnistack` strings remain in `storage.py` APP_NAME and the plugin manifest
  `format: omnistack.plugin` (not visible in the UI, but visible inside exported plugin zips)

## Order agreed with user
ElevenLabs → External DB sync → Delete-my-account → GitHub push (PAT on hold)

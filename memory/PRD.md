# PRD — OmniStack AI (Agency Showcase & Multi-Tenant App Platform)

## Problem
Production-ready platform for an agency to host, manage, showcase and hand off multiple client
web/mobile apps from one workspace. Framer-style visual Site Mode + Lovable-style conversational
App Mode, multi-tenant with client portals.

## Personas
- Agency owner (Jay @ Lucio Digital) — creates, manages, bills and hands off tenants.
- Client — invited as viewer/editor/admin to their own tenant only.

## Core Requirements
1. Master dashboard — client cards, status pills, metrics, industry/kind filters, search.
2. Site Mode — multi-page block builder, dnd, themes, inline text/image editing, niches, effects.
3. App Mode — blueprint (screens/models/API/roles), conversational refinement, 18 industry templates.
4. Client Handoff & Export — .zip bundle (site + app + mobile), GitHub sync, live preview links.
5. Multi-tenant RBAC, activity log, notifications, client portal + voting.
6. AI Media Studio, Lead Inbox with AI scoring + replies, Workflows, CMS, Files, Billing, Domains.
7. Per-tenant data destinations (own Postgres/Supabase/Drive/Dropbox/OneDrive).

## Implemented (condensed — full history in earlier versions of this file / activity logs)
- v1–v17 (Feb–Jun 2026): auth (JWT + Emergent Google), apps CRUD, block builder, exports, RBAC,
  AI Media Studio, Stripe billing, custom domains, multi-page studio + prompt-to-site/app, Lead
  Inbox + AI scoring + inline AI replies with attachments, chat embed + widget, GitHub sync (PAT),
  workflow engine + email, Deployment Hub, CMS collections, client portal, growth/effects, premium
  motion system, page transitions, 18 industry templates, premium dark design system + 16 niche
  packs, niche switcher + look voting, brand preservation, logo upload, inline image swap, landing
  page admin CMS, tenant label CMS, inline text toolbar, Cursor Effects Engine (+intensity, client
  vote), builder undo/draft recovery, File & Media library on Emergent Object Storage with quotas
  and data export, per-tenant data destinations, canvas library image picker.
- Tests: iteration_2 … iteration_26 all passing.

### Jun 2026 (v18) — Site → App AI sync + Website import (iter 27)
- **Site → App AI sync** (`/app/backend/site_sync.py`): `site_snapshot()` collects the tenant's
  brand, industry, niche, theme colours, contact profile, CMS collections and the full text of every
  Site Mode page/block. Claude then designs the companion app so every service, plan, location,
  team section and form on the website maps to a screen, model or field in the blueprint.
  - `POST /api/apps/{id}/ai/app-from-site {mode: merge|overwrite}` → starts a background job
    (`GET /api/apps/{id}/ai/app-sync-job/{job_id}` polls; the 60s ingress cap makes sync responses
    unsafe). `merge` preserves screens/models the owner added by hand; `overwrite` rebuilds.
  - `GET/POST /api/apps/{id}/site-sync {enabled}` → per-tenant auto-sync toggle. `studio.update_page`
    calls the `maybe_site_sync` hook after every page save; a content fingerprint skips no-op syncs
    and an in-flight lock prevents duplicate parallel LLM runs.
  - UI in App Mode (`BlueprintPanel.jsx`): `app-sync-btn` ("Build / Re-sync app from my site"),
    `app-sync-toggle`, `app-sync-summary`, `app-sync-status`; each sync is logged into the App Mode
    chat history and the activity log.
- **Website import / scraper** (`/app/backend/web_import.py`): paste any public URL → httpx +
  BeautifulSoup scrape of the home page plus up to 4 relevant internal pages (headings, paragraphs,
  lists, images with alts, nav links, emails, phones, logo/og:image, theme-color and the strongest
  brand hex colours), then Claude rebuilds it as editable Site Mode pages using only real scraped
  facts and image URLs.
  - Jobs: `POST /api/apps/{id}/site/import-preview {url}` → `{job_id}`; poll
    `GET /api/apps/{id}/site/import-job/{job_id}`; `POST /api/apps/{id}/site/import-apply
    {import_id, mode: replace|append, apply_theme}`; `POST /api/apps/{id}/site/import` (one-shot job
    used by the new-project flow). SSRF/localhost guards + friendly 400s on bad URLs.
  - Places available: Dashboard → New project modal (`new-app-url-input`, optional) and inside each
    tenant → Site Mode toolbar `web-import-btn` (`WebImport.jsx` dialog with scan → preview of
    business details, brand swatches and pages → replace/append + "use the website's colours" →
    apply). Import also writes the tenant's brand_profile (email/phone/address) and thumbnail.
- **Testing**: iteration_27.json — backend 10/10 pytest (both suites), frontend 100%; verified with
  a real scrape of roto-rooter.com (correct brand, phone, colours, 5 pages) and merge-mode sync
  preserving prior screens.

## Backlog (P1/P2)
- P1: Real GitHub push — waiting on the user's Personal Access Token (currently MOCKED without one).
- P1: ElevenLabs voice — waiting on the user's API key (falls back to OpenAI TTS).
- P1: Resend email — Emergent managed email is live; switch to the managed Resend playbook if the
  user wants Resend branding/domains.
- P1: Execute (not just store) the external data-destination syncs once clients supply credentials.
- P1: Landing demo section still uses placeholder clips.
- P2: Undo for a "replace" website import (snapshot previous pages before deleting).
- P2: Progress steps (Scanning → Building → Applying) for the ~90s import job.
- P2: Lead follow-up sequences (second AI email after 48h with no reply).
- P2: Edit-mode on/off switch for the landing page admin CMS.
- P2: Real CI/CD for mobile builds; Stripe customer portal; audit-log CSV export.

## Notes
- Cloudflare ingress kills requests at 60s → every scrape/LLM pipeline must be a polled job.
- Cursor: dot + particle trails only. Never reintroduce the outer cursor ring.
- All uploads go through Emergent Object Storage (`backend/storage.py`, `files_lib.py`).

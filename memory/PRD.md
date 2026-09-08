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

### Jun 2026 (v19) — Import progress + 48h lead follow-ups (iter 28)
- **Import progress**: the import job now records `stage` / `stage_detail` / `stage_at`
  (`queued → scanning → reading (n of m) → rebuilding → applying → done`). Stage writes are awaited
  in order (an earlier fire-and-forget version raced and clobbered `applying`). `ImportProgress`
  (in `WebImport.jsx`) renders an animated stepper with ticks, the live detail line and an
  elapsed-seconds counter — used in the Site Mode import dialog (`web-import-progress`) and the
  Dashboard new-project modal (`new-app-import-progress`).
- **48h AI lead follow-ups** (`/app/backend/followups.py`): hourly platform cron
  (`.emergent/crons.yml` → `POST /api/cron/lead-followups`, bearer `WEBHOOK_CRON_SECRET`, acks
  immediately + `X-Webhook-Id` idempotency) scans tenants with `followups_enabled` and queues ONE
  AI follow-up **draft** per quiet lead — both for leads we replied to 48h+ ago (`kind: replied`)
  and leads nobody ever answered (`kind: no_reply`). Nothing is auto-sent: drafts land in the Inbox
  for one-click approval. Skips archived leads, leads without an email, and already-followed leads.
  - Endpoints: `GET/POST /api/apps/{id}/inbox/followups {enabled}` (default OFF),
    `POST /api/apps/{id}/inbox/{mid}/followup-draft|followup-approve|followup-dismiss`.
  - UI in `InboxPanel.jsx`: sidebar toggle + pending-draft badge, per-lead row badges, and an
    editable draft card with Approve & send / Rewrite / Dismiss.
- Testing: iteration_28.json — backend 12/12 pytest, frontend verified; the one reported issue
  (unobservable `applying` stage) was fixed by awaiting the stage callbacks.

### Jun 2026 (v20) — Full-site crawl importer (iter 29)
- `web_import.py` rewritten from a single-page scrape into a **full crawl**: BFS over internal links
  (25 pages max, depth 2, skipping blog archives/pagination/assets), ranked so real pages
  (services/about/pricing/contact) come first. Each crawled page becomes its own tenant page.
- **Media**: every image (incl. `srcset`, `<source>`, CSS `url()`, `og:image`, logo) is downloaded
  into the tenant's library via Emergent Object Storage (80 images / 8 MB each, quota-aware,
  `uploaded_by: website import`, public) and page blocks reference only `/api/public/files/...` —
  nothing is hotlinked. Admins can also upload their own images/videos/docs from the import dialog.
- **Forms**: every `<form>` is parsed field-by-field (label via `for`/aria/placeholder, type, options,
  required) and rebuilt as a new **`form` block type** (renderer in `BlockPreview.jsx`, palette entry in
  `Builder.jsx`, schema entry in `studio.py`) whose submissions post to `/api/public/contact/{token}`
  and land in the tenant Inbox. JS-rendered forms fall back to a standard contact form and are listed
  in the report.
- **Navigation**: header nav is recreated with dropdown `children` (rendered on hover), shared across
  every imported page, with a footer block on each page.
- **Colours**: inline styles + up to 3 stylesheets are parsed into background / text / button colour
  buckets (hex + rgb) and turned into the tenant theme.
- **Report**: pages crawled/imported, images saved vs found, forms rebuilt, nav items + dropdowns, and
  a failure list with reasons (unreachable page, oversized image, quota reached, JS-rendered form) —
  shown in the import dialog and after a new-project import.
- Fixes found while building: LLMs returning `{label, href}` where a string belongs (now sanitised
  server-side + defensively in `T()`), footer link objects crashing the canvas, and the startup
  premium-redesign migration wiping imported pages (imports now set `premium_site_v: 3`).
- Testing: iteration_29.json — backend 16/16 pytest, frontend verified (no canvas crash, dropdowns,
  form render + Inbox wiring).

### Jun 2026 (v21) — Form routing, 100-page crawl with page picking, Video Studio (iter 30)
- **Optional per-form routing**: each Form block can name a team member (from `/apps/{id}/members`) or
  any email in the Site Mode panel (`FormRouting` in `Panels.jsx`). Submissions always land in the Lead
  Inbox; when a recipient is set that person also gets the submission by email and the lead carries a
  `routing` object (form_id, form_name, form_page, notify_email, assignee). Routing is resolved from
  the STORED block only — the public payload just carries `form_id`, so no open relay and no
  cross-tenant leak (page lookup is app-scoped; unresolvable form ids attach no routing).
- **Deeper crawl + page picking**: `MAX_PAGES` 100 / `MAX_DEPTH` 3. New `POST /site/discover` runs a
  fast crawl with NO AI and NO downloads and returns every page found (title, words, images, forms,
  videos, `important` flag) plus totals; the dialog shows a checklist (Important only / Select all /
  Clear) and `POST /site/import-selected {discovery_id, slugs[]}` rebuilds only the ticked pages.
  The old one-shot "Crawl everything" flow remains for the new-project modal.
- **Video Studio** (`/app/backend/videos.py`, `VideoStudio.jsx`, new "Videos" tab):
  - Free stock sourcing from **Pexels + Pixabay** — search, auto-source by the tenant's niche,
    download and self-host in the tenant library (no hotlinking, 60 MB cap, quota-aware, provenance
    kept: provider, source_url, contributor, license_review_required). Needs `PEXELS_API_KEY` and/or
    `PIXABAY_API_KEY` in backend/.env — **not yet supplied**, so those endpoints return a friendly 400.
  - **AI video generation** via fal.ai on the Emergent Universal Key: `fal-ai/veo3.1` and
    `fal-ai/kling-video/o3/pro/text-to-video` (queue submit → poll → download → library → placed on
    the site). Verified live: a 13.8 MB Kling O3 Pro clip generated and placed on the home page.
  - Upload your own videos, and one-click "Place on the site" (idempotent video block after the hero).
  - Imports now also embed YouTube/Vimeo videos found on the crawled site and, when stock keys exist,
    auto-source 1-2 niche-matched clips (`_auto_videos`) as part of the import job.
- Testing: iteration_30.json — backend 23/23 pytest, frontend smoke 100%; the reported routing
  metadata-pollution nit was fixed (no routing object for unresolvable form ids).

## Backlog (P1/P2)
- P1: Real GitHub push — waiting on the user's Personal Access Token (currently MOCKED without one).
- P1: Add `PEXELS_API_KEY` / `PIXABAY_API_KEY` to backend/.env to switch on free stock video sourcing
  (UI and backend are complete and degrade gracefully until then).
- P1: ElevenLabs voice — waiting on the user's API key (falls back to OpenAI TTS).
- P1: Resend email — Emergent managed email is live; switch to the managed Resend playbook if the
  user wants Resend branding/domains.
- P1: Execute (not just store) the external data-destination syncs once clients supply credentials.
- P1: Landing demo section still uses placeholder clips.
- P2: Undo for a "replace" website import (snapshot previous pages before deleting).
- P2: Progress steps (Scanning → Building → Applying) for the ~90s import job.
- P2: Edit-mode on/off switch for the landing page admin CMS.
- P2: Remember the last-selected tenant tab across reloads (Inbox/Site Mode resets to Overview).
- P2: Second follow-up in the sequence (a third touch) + a per-tenant follow-up delay setting.
- P2: Crawl deeper than depth 2 / more than 25 pages for large sites (currently capped).
- P2: Import undo — snapshot pages before a 'replace' import.
- P2: Real CI/CD for mobile builds; Stripe customer portal; audit-log CSV export.

## Notes
- Cloudflare ingress kills requests at 60s → every scrape/LLM pipeline must be a polled job.
- Cursor: dot + particle trails only. Never reintroduce the outer cursor ring.
- All uploads go through Emergent Object Storage (`backend/storage.py`, `files_lib.py`).

# PRD — Agency Showcase & Multi-Tenant App Platform

## Problem
Build a production-ready dashboard for an agency to host, manage, showcase and hand off multiple distinct client web/mobile apps from a single workspace. Website styled like framer.com.

## Personas
- Agency owner (Jay @ Lucio Digital) — creates, manages, bills and hands off apps.
- Client — invited as viewer/editor/admin to their own app tenant only.

## Core Requirements
1. Master agency dashboard — 5+ client app cards, status pills, metrics, industry filter, search.
2. Block builder — hero, features, pricing, contact, chart blocks; real drag-and-drop (@dnd-kit); Claude AI prompt editor.
3. Client Handoff & Export — .zip source bundle (real), iOS/Android builds (MOCKED), Client Transfer Mode, Live Preview Link.
4. Multi-tenant RBAC — owner/admin/editor/viewer roles per app, activity log, notifications.
5. Dual auth — JWT email/password + Emergent Google OAuth.
6. AI Media Studio — GPT-Image-1 images, fal.ai (Hailuo-02) video, ElevenLabs voiceover (key added in-app).
7. Stripe billing per tenant — plan tiers, pricing import from .xlsx/.csv/.docx, checkout, status polling, webhook.
8. Custom domains — real DNS (CNAME + TXT) lookup, status badge.

## Implemented
### Feb 2026 (v1)
- Backend: FastAPI + Mongo, dual auth, apps CRUD, pages/blocks, memberships/RBAC, activity logs, notifications, .zip export, MOCKED mobile export, Claude Sonnet 5 AI block editor.
- Frontend: Landing, Login/Register + Google, Dashboard grid with filters, App detail tabs, builder.
### Jun 2026 (v2) — all in `/app/backend/extras.py` + new frontend components
- AI Media Studio tab (`MediaStudio.jsx`): image (gpt-image-1, Emergent key), video (fal.ai via Universal Key proxy, background task + polling), voice (ElevenLabs; key stored in `db.settings`, highlighted "Add ElevenLabs key" button; 503 until configured).
- Billing tab (`BillingPanel.jsx`): Stripe claimable sandbox (Flow A, tax mode "full" w/ fallback), plan catalog per owner in `db.plan_catalogs`, import parser (openpyxl/python-docx/csv) → Stripe products/prices by lookup_key, checkout, `/payment/success|cancel` pages, `/api/stripe/webhook`.
- Domain tab (`DomainPanel.jsx`): real dnspython lookups, CNAME target `tenants.luciostudio.app`, TXT `_lucio-verify.<domain>`, statuses pending/partial/verified.
- Live preview (`PreviewLinkCard.jsx`, `/p/:token` → `PublicPreview.jsx`, `GET /api/public/preview/{token}`), regenerate revokes old token, enable toggle.
- Builder rewritten with @dnd-kit sortable outline + canvas drag handles.
- Landing redesigned Framer-style (pill nav, centered hero, marquee, bento grid, pricing teaser, motion reveals). Guidelines: `/app/design_guidelines_framer.md`.
- Testing: iteration_2.json — 17/17 new backend + 22/22 regression pass; frontend flows verified.

### Jun 2026 (v3) — Framer/Lovable studio (`/app/backend/studio.py`, `/app/backend/export_gen.py`)
- Multi-page website builder: page tabs (create/delete, home protected), 13 block types, per-block style (bg/align/padding, hero variants), per-tenant theme (light default, orange #F97316 + turquoise #14B8A6, fonts, radius, dark mode), inline contentEditable text editing, device toggle, dnd reorder.
- Prompt-to-site (Claude Sonnet 5) generates full multi-page site + theme; AI block editor retained.
- App Blueprint tab: prompt-to-app spec (screens, models, API, roles) rendered as navigable prototype; .zip export now has `site/` (multi-page HTML + styles.css) and `app/` (React + FastAPI + Mongo starter with CRUD per model).
- Public preview `/p/<token>` is multi-page + themed + live AI chat widget (Claude, session history in `db.chat_messages`, OpenAI tts-1 voice via `/api/public/tts`, browser mic). Landing also has the chat widget (token `studio`).
- Testing: iteration_3.json — 14/14 backend, frontend flows pass.

### Jun 2026 (v4) — OmniStack AI rebrand + agency ops (`/app/backend/inbox.py`, `seed_sites.py`)
- Rebrand to **OmniStack AI**; projects have `kind` website|app (dashboard filters, New project modal selector); tabs renamed Site Mode / App Mode.
- **Lead Inbox** tab per app (`db.messages`): contact-form submissions from public preview (`POST /public/contact/{token}`) + AI chat conversations (upserted per session) → Gmail-like list with unread/star/archive/reply/delete; global `GET /inbox` + unread badge on dashboard. Reply email delivery is QUEUED (no provider yet).
- **Chat embed**: `GET /api/public/embed.js` + `/embed/chat/:token` iframe page; snippet card in Handoff; auto-injected into exported HTML.
- **GitHub Sync**: PAT stored in `db.settings` (`POST /settings/github` validates), `POST /apps/{id}/github/push` real push via Git Data API when token present, MOCKED status otherwise; auto-sync toggle pushes on every page save.
- **AI images in blocks**: "Generate with AI" on hero `image` / gallery `images` props (gpt-image-1).
- Export bundle: `site/` (+embed), `app/` (+ `backend/schema.sql` Postgres/Supabase), `mobile/` (Capacitor + App Store / Google Play steps). Native build automation remains MOCKED.
- Seeded demo apps reseeded (`demo_site_v=2`) with unique themes (light/dark, fonts, colors), 4 pages each, niche Unsplash imagery and videos. TTS prefers ElevenLabs when key configured.
- Testing: iteration_4.json — 15/15 backend, frontend flows pass.

### Jun 2026 (v5) — Workflow engine, App Mode chat, Deployment Hub (`/app/backend/workflows.py`)
- **Workflow Engine** tab: triggers (form_submitted, chat_lead, payment_succeeded, member_invited, page_published) → conditions (==, !=, contains, >, <) → actions (email via Emergent managed mail w/ guardrail gate, db_write → `db.workflow_records`, webhook POST, notify → activity log). Step builder UI, Test run with sample payloads, enable toggle, run stats. Hooks fire from contact form, chat leads, Stripe paid.
- **Email**: Emergent managed email (EMERGENT_EMAIL_KEY, EMAIL_FROM_NAME=OmniStack AI, reply-to jaybernabe@luciodigital.com). Inbox replies email the lead (delivery email_sent) — recipients always server-side.
- **App Mode chat**: split-screen chat (`POST /apps/{id}/ai/refine-app`, history `GET .../ai/app-chat`), click prototype components to target them; Claude returns updated spec + summary.
- **Deployment Hub** `/deploy`: all projects with Live/Draft, domain, GitHub status lights; publish/unpublish, push.
- Tablet viewport in Site Mode; landing image strip; buttons glow on :active.
- Testing: iteration_5.json — 10/10 backend, frontend pass.

## Phase 2 (next) — OmniStack spec items not yet built
- CMS collections (blog posts / case studies) bound to list & detail blocks.
- Real sandboxed React code preview in App Mode (currently structured prototype from blueprint), GitHub OAuth app (PAT today), Stripe customer portal.

### Jun 2026 (v6) — CMS, Client Portal, Workflow templates (`/app/backend/cms.py`)
- **CMS** tab: collections per app (defaults Blog posts `/blog`, Case studies `/case-studies`, custom), items (title/slug/excerpt/body/cover/date/tags/published). `collection_list` block renders cards + in-place detail view; public site ships collections; export writes `site/<collection>/<slug>.html`.
- **Client Portal** `/portal` (same login; clients invited via Members): live link, invoices, leads, activity, "Request a change" → Inbox (source `request`) + `change_requested` workflow trigger.
- **Workflow templates**: 6 recipes (`GET /workflows/templates`, `POST /apps/{id}/workflows/templates/{key}`); new projects auto-install welcome_lead, log_chat, change_request. Templates picker in Workflows tab.
- App Mode: upload .docx/.pdf/.txt/.md or paste a long narrative (`POST /apps/{id}/ai/brief-upload`) → used as brief or applied as a refine request; prototype pane has a themed gradient background.
- Testing: iteration_6.json — 14/14 backend, frontend pass.

### Jun 2026 (v7) — Growth & effects (`/app/backend/growth.py`, `EffectWrap.jsx`, `CursorTrail.jsx`)
- **AI credit protection**: clients (viewer/editor members) get 403 on all AI/media endpoints (`require_ai_access`); only owner/admin can spend credits.
- **Built-in effects**: per-block toggles (scroll reveal, parallax, hover lift, floating) via framer-motion EffectWrap; theme toggles `motion` / `cursor`; **custom lerp cursor trail** on OmniStack + public sites; exported HTML ships fx CSS/JS + cursor script (omitted when both off).
- **Site analytics**: `POST /public/track/{token}` beacon from public sites → `GET /apps/{id}/analytics` (views, visitors, top pages, daily, chat convos, leads, conversion) shown as AnalyticsCard in Overview.
- **AI Blog Writer**: `POST /apps/{id}/cms/{col}/ai-write` (Claude post + GPT-Image cover) → draft CMS item; UI in CMS tab. `_parse_json` now strict=False.
- **Portal invites**: `POST /apps/{id}/portal/invite` emails a one-time 7-day magic link (`GET /api/auth/magic/{token}` → cookies → /portal); fallback copy-link when email fails; UI in Members tab.
- Testing: iteration_7.json — 8/9 backend then ai-write fixed & verified; frontend pass.

### Jun 2026 (v8) — Premium motion system (`/app/frontend/src/components/motion.jsx`, index.css "Premium motion system")
- Landing: word-by-word headline, pulsing hero glow, shimmer badge, glow buttons, cursor spotlight, sliding nav pill (layoutId), showcase/bento/pricing `card-lift` glow, LIVE `badge-glow`, arrow-slide, Pro `pro-glow`, shimmer-on-hover buttons, CTA `gradient-border` scale-in + `icon-shimmer` + `pulse-soft`.
- Dashboard: CountUp stats, motion headline, staggered fade-up cards, card-lift, badge-glow status chips, sliding filter indicators.
- Builder/AI/seed defaults: every new/generated/seeded block gets `effects {reveal:true, hover:true for card-type blocks}`; DEFAULT_THEME radius 20; generate-site prompt enforces premium SaaS aesthetic; demo sites regenerated.
- Testing: iteration_8.json — 4/4 backend, frontend pass, no issues.

### Jun 2026 (v9) — Page transitions + AI lead scoring
- Route transitions via AnimatePresence (`PageTransition.jsx`, testids page-dashboard/app/deploy/portal) and skeleton shimmers (`.skeleton`, `PageSkeleton`, dashboard skeleton cards).
- Lead scoring (`inbox.py` `score_message`): every new contact/chat/request lead is auto-scored by Claude in the background (score 0–100, intent, reason, hot ≥70); inbox sorted hot → score → recency; "Hot leads" filter + count, "Score N leads" batch button, score badge + reason in detail; `POST /apps/{id}/inbox/score`, `POST /apps/{id}/inbox/{mid}/score`.
- Testing: iteration_9.json — 5/5 backend, frontend pass.

### Jun 2026 (v10) — Industry templates, premium dark redesign, Leads page, showcase demos
- **18 industry templates** (`templates.py`): App Mode prototype uses industry accent for Save/chart/chat/kanban/calendar mocks; exported React starter has fixed left sidebar + breadcrumbs + industry theme (`starter_app_files(spec, theme)`, `theme.json`).
- **Landing "See it in action"** demos section (demo-video-0..2, placeholder clips); Members remove button testid.
- **Premium site design system** (`site_content.py`): dark default theme (bg #0A0A0F, glass cards `.tglass`, grain `.tgrain`, glow borders), hero variant `cover` (full-width image + cinematic gradient), new blocks `stats` + `team`, YouTube iframe support in video blocks, alternating section bgs. 11 hand-written niche content packs (hvac, healthcare, construction, fitness, retail, hospitality, finance, it_services, creative_studio, logistics, saas) with brand, team, stats, testimonials w/ results, pricing, FAQ, about story, contact, industry-correct section order. Applied retroactively on startup (`premium_site_v=3`) to every tenant; `POST /apps/{id}/site/premium-rebuild {niche?}`, `GET /site-niches`; "Premium redesign" button in Site Mode. AI generate-site prompt enforces dark premium + Layer 1–3 content + industry section structure. Export CSS/HTML updated (glass, grain, cover hero, team/stats, YouTube).
- **Leads page** `/leads` (`Leads.jsx`): dashboard chip `dashboard-inbox-badge` is clickable; table (name/contact/source/date/status/score), detail aside, filters, mark reviewed/new/archive/star, mark-all; count updates live and on dashboard return.
- **Showcase cards** on Landing open the live demo (`GET /public/showcase` → `/p/<token>`) with a transition overlay, or a NicheModal with description + Get started / Request a demo when no demo exists.
- Testing: iteration_10.json (templates 21/21), iteration_11.json (12/12 backend, all frontend flows pass).

### Jun 2026 (v11) — Niche Switcher + 5 more niche packs
- 16 niche packs total: added legal (Whitfield & Grant LLP), education (Brightwater Academy), real_estate (Harbour & Vale Realty), restaurant (Ember & Oak), events (Lumen Events Co.); INDUSTRY_MAP routes those industries directly.
- **Niche Switcher** in Site Mode (`NicheSwitcher.jsx`, "Try another look" `niche-switcher-btn`): `POST /apps/{id}/site/niche-preview {niche}` returns a non-destructive 4-page preview + theme; Builder shows `niche-preview-bar` + `niche-preview-canvas` with page pills; "Apply this look" calls premium-rebuild; "Back to my site" restores.
- Testing: iteration_12.json — 16/16 backend, frontend flows pass.

### Jun 2026 (v12) — Lead Reply Inline, Client Look Voting, Brand Preservation, tenant app standards
- **Lead Reply Inline** (`LeadReply.jsx` on /leads): `POST /apps/{id}/inbox/{mid}/ai-draft` (Claude) drafts a reply; composer expands inline (framer-motion), sends via existing reply endpoint (email via Resend when address present), reply history + delivery status on the card, status chip "Replied".
- **Client Look Voting** (`LookVoting.jsx` in /portal): `GET /apps/{id}/site/look-options` (5 curated looks: current + 2 same-mood + 2 contrasting), `POST /apps/{id}/site/look-vote` stores `apps.look_vote` and logs `look.voted` (owner notifications). Owner sees `ClientVoteBanner` in Site Mode → Preview & apply; applying the voted niche sets `look_vote.applied`.
- **Brand Preservation** (`extract_brand`): tenant name/email/phone/address/logo pulled from `apps.brand_profile` + existing contact/navbar blocks; pack sample values and placeholders (example.com) are never treated as real. `niche-preview`/`premium-rebuild` return `preserved`; `apply-look-confirm` dialog lists preserved fields before applying.
- **Tenant app standards** (App Mode export): `<html class='light'>`, dark-mode toggle in sidebar, `.dark` vars, scroll-reveal `.reveal`, scale-on-hover, idle float keyframe; template palette map updated (Finance navy/emerald, Legal burgundy, Logistics steel blue, Education indigo, Restaurants amber, Events purple, IT cyan, Real Estate forest green).
- Testing: iteration_13.json (all pass except stale banner) → fixed → iteration_14.json.

### Jun 2026 (v13) — Tenant Logo Upload
- `storage.py` (Emergent Object Storage): `POST /apps/{id}/brand/logo` (multipart, PNG/JPG/SVG/WEBP/GIF ≤2MB) stores object at `omnistack/logos/{app_id}/{uuid}.{ext}`, records in `db.files`, sets `apps.logo` + `brand_profile.logo`, and writes `props.logo` into every navbar/footer block; `DELETE` removes; `GET /public/files/{path}` serves publicly (immutable cache).
- Logo renders in BlockPreview navbar/footer (`navbar-logo`/`footer-logo`), is preserved through niche previews/applies (`brand_logo`), and is bundled into exports as `site/assets/logo.<ext>` (HTML rewritten) + starter app sidebar brand.
- UI: `LogoUpload.jsx` in Site Mode toolbar (`logo-upload-btn`, `logo-file-input`, `logo-current`, `logo-remove-btn`).

### Jun 2026 (v14) — Inline text editing on every block
- BlockPreview `T` (contentEditable) now covers all remaining text: nav link labels, navbar CTA, stats kicker, logo-cloud names, pricing feature lines, footer column links, chart labels (paths like `plans.0.features.2`). Canvas hint `inline-edit-hint`. Verified: 103 editable elements on a Home page; edits mark the page dirty for Save.

### Jun 2026 (v15) — Landing page admin CMS
- `landing_cms.py`: `GET /public/landing` (cards, marquee, texts with defaults) and admin-only `PUT /admin/landing` (partial patch; admin = ADMIN_EMAIL). `/auth/me` now returns `is_admin`. Stored in `site_settings` {key:'landing'}.
- `LandingAdmin.jsx`: hover edit/delete controls on niche cards (`card-edit-btn`/`card-delete-btn`, confirm on delete), `CardEditor` modal (title/description/cover image), `card-add-btn`; `MarqueeEditor` (`marquee-edit-btn`, add/rename/remove items); `AdminText` click-to-edit headlines (`text-hero-caption-title` "B2B Success Analytics", section overlines/headings, CTA heading). Visitors see plain content only.

### Jun 2026 (v16) — Inline image swap, all-landing-text editing, pricing + demo video editing
- **Inline Image Swap** (`ImageSwap.jsx`): hover "Replace image" overlay on hero (split/cover), gallery images, team photos in the Site Mode canvas (`image-swap-<path>`); dialog with Upload (`POST /apps/{id}/media/upload` → object storage), Generate with AI (gpt-image-1), Paste URL; applies via editProps → Save.
- **Landing texts**: `PUT /admin/landing` texts now accept any key; `Tx` helper wraps every landing text (brand name, hero eyebrow/h1/sub/CTAs, showcase, demos sub, bento titles/descs, pricing overline/heading/sub + tier name/price/period/desc/CTA (`text-pricing_i_*`), footer CTA/copyright). Admin click → type → blur saves to DB.
- **Demo videos**: admin "Set video URL" chip per demo (`demo-video-url-i`, MP4 or YouTube embed) + editable demo titles; stored as `demo_i_video` text keys.

## Backlog (P1/P2)
- P1: Landing demo section uses placeholder clips — swap for real product walkthrough videos when user provides them.
- P1: User adds ElevenLabs key (button in AI Media tab) — voice untested with a real key.
- P1: Move generated media (base64 in Mongo, fal temp URLs) to Emergent Object Storage.
- P2: Real CI/CD for mobile builds (currently MOCKED).
- P2: Team-level audit log CSV export; password reset email flow (Resend).
- P2: Stripe customer portal / cancel subscription; per-plan feature gating.
- Cosmetic: Radix Dialog aria-describedby warning; /auth/me 401 on public pages.

## Stripe notes
- Sandbox account CA (`acct_1UCqXZRU6y7XBGGy`), keys in backend/.env. Claim link shared with user in finish summary. Tax mode: Stripe-managed (full) with automatic fallback to calc-only.

## 2026-06 — Tenant Overview Label CMS (DONE)
- New `/app/backend/ui_cms.py`: GET/PUT/DELETE `/api/apps/{app_id}/ui_labels`. Tenant labels in `apps.ui_overrides`; global defaults in `site_settings` key `ui_labels`. Merge = global then tenant override. Edit allowed for platform admin (ADMIN_EMAIL) or app owner; keys sanitized (no `.`/`$`).
- New `/app/frontend/src/components/UiLabels.jsx`: `UiLabelsProvider`, `<L k d>` inline contentEditable label (saves on blur + "Saved" toast), `UiLabelsToolbar` with "Apply to all tenants" and "Reset all".
- Wired into AppDetail.jsx (Tenant overline, tenant name, all 12 tab labels), OverviewPanel.jsx (Lifecycle status, Live hosting metrics + metric labels, Visitors 24h, Quick links, card title/desc), AnalyticsCard.jsx (analytics heading/subheading, 5 stat titles, Daily views, Top pages).
- Tested: iteration_19.json — backend 10/10 pytest, frontend 100% (persistence, per-tenant scoping, permission gating, tab nav intact).

## 2026-06 — Inline text toolbar, chat attachments, Cursor Effects Engine (DONE)
### Inline text styling + undo (iter 20)
- `/app/frontend/src/components/InlineTextTools.jsx`: `EditableText` — click-to-edit with Ctrl+Z undo stack, floating toolbar (8 fonts: Inter, Poppins, Roboto, Playfair Display, Space Grotesk, DM Sans, Sora, Outfit + colour picker + Clear), dismisses on outside click. Used by Overview labels (`UiLabels.L`) and the Site Mode canvas (`BlockPreview.T`).
- Styles persist per tenant: `apps.ui_label_styles` (Overview) and `block.props._styles` (canvas, saved with the page). Global defaults in `site_settings.ui_labels.styles`.
- Fix: inline label click no longer swallows parent tab-button clicks (iter-20 regression).
### Chat widget (iter 21)
- Blank input placeholder; attachment button + `POST /api/public/chat/{token}/upload` (images, PDF, DOC/X, XLS/X, CSV, TXT, ZIP; 10 MB cap; Emergent Object Storage; records in `db.files`).
- Chat text colour defaults to `#000000`, admin-editable from a colour picker in the widget header, persisted as landing CMS key `chat_text_color`; bubbles auto-lighten for contrast.
### Cursor Effects Engine (iter 22)
- `/app/frontend/src/lib/cursorEffects.js` + `/app/frontend/src/components/CursorFX.jsx`: canvas engine with 10 trails (fairy, bubbles, smoke, fire, wind, frost, plasma, ink, comet, matrix) + None, capped at 260 particles, auto-off on coarse pointer / reduced motion.
- Picker (`cursor-fx-picker-btn`) in the Dashboard and tenant headers with hover-to-try preview; saved per user via `PATCH /api/me/preferences` and cached in localStorage.
- Per-tenant effect via ThemePanel `theme.cursor_effect` — drives the public preview and is injected into exported sites (`CURSOR_FX_JS` in export_gen).
- Tested: iteration_20/21/22.json — all backend + frontend cases pass (all 10 effects verified painting).

## 2026-06 — Intensity, client cursor vote, builder undo, attachment inbox (iter 23, DONE)
- **Effect Intensity**: `startCursorFX(canvas, effect, accent, {density, speed})` scales spawn count, particle size, velocity and decay. Per-user sliders in the header picker (`cursor-fx-density-slider` / `cursor-fx-speed-slider`, debounced `PATCH /api/me/preferences` with 0.2–3.0 clamp + localStorage) and per-tenant sliders in ThemePanel (`theme.cursor_density` / `cursor_speed`) that flow into the public preview and exported ZIP (`data-cursor-density` / `data-cursor-speed`).
- **Client Effect Choice**: `/app/frontend/src/components/CursorFXVoting.jsx` in the client portal — hover to try, vote via `POST /apps/{id}/cursor-vote`; agency sees `cursor-vote-banner` in Site Mode and applies with `POST /apps/{id}/cursor-vote/apply` (owner/admin only, members get 403). Stored on `apps.cursor_vote`.
- **Undo History**: `Builder.jsx` keeps a 50-step `{past, future}` stack; every `mutate()` (add/delete/reorder/prop edit/AI edit) is undoable via Ctrl+Z, redo via Ctrl+Shift+Z, plus `builder-undo-btn` / `builder-redo-btn`. Inline text Ctrl+Z stops propagation so typing undo stays local.
- **Attachment Inbox**: `/app/frontend/src/components/Attachments.jsx` parses `[attachment] name — url` (and bare `/api/public/files/...`) out of lead bodies; pill on Inbox/Leads rows, thumbnail grid in both detail panes, click opens the file.
- Tested: iteration_23.json — backend 9/9 pytest, frontend 100%, no issues.
- Known nit (not fixed, non-blocking): no endpoint to clear a cursor vote; attachments are parsed from body text rather than a dedicated field.
- Base cursor dot + ring now recolour automatically from the active effect's swatch (`CursorTrailThemed` in CursorFX.jsx); falls back to green when the effect is None.
- Removed the trailing ring/big circle from the custom cursor across the workspace, all tenant pages, public previews and exported sites (`CursorTrail` now renders only the dot; export FX_JS ring removed).

## 2026-06 — Reply with files + builder draft recovery (iter 24, DONE)
- **Reply With Files**: `POST /api/apps/{app_id}/attachments` (auth, 15 MB, CHAT_MIME allowlist, object storage). `ReplyIn` now takes `attachments:[{name,url}]` (max 10, stored on the reply, links appended to the outgoing email; 400 when body and attachments are both empty). `LeadReply.jsx` gained an Attach button, chip list with remove, attachment-only sending, and thumbnails in the reply history. The tenant Inbox tab now reuses `LeadReply` so its composer supports attachments + AI drafts too (its old textarea composer was removed).
- **Draft Recovery**: `Builder.jsx` writes unsaved blocks to `os_builder_draft_{app_id}_{page_id}` (debounced while dirty), detects a stale draft on load/page switch and shows `builder-draft-banner` with Restore / Discard; the draft clears on save.
- Tested: iteration_24.json — backend 10/10 pytest, frontend 100%. Follow-up flagged by the tester and fixed after the run: Inbox-tab composer now supports attachments.

## 2026-06 — File & Media Storage integration (iter 25, DONE)
- `/app/backend/files_lib.py` (registered in server.py): per-tenant library on Emergent Object Storage per the official playbook — `POST/GET /api/apps/{id}/files`, `GET /files/usage`, `PATCH /files/{id}` (rename), `PATCH /files/{id}/privacy`, `GET /files/{id}/download` (authenticated), `DELETE /files/{id}` (soft delete; storage has no delete API). MongoDB `db.files` stays the source of truth.
- Quota: 500 MB default (`TENANT_STORAGE_QUOTA_MB`), per-app override via `apps.storage_quota_mb`; 413 on overflow; usage bar shown in the Files tab and in Billing (`StorageUsageBar`).
- Privacy: library uploads are `private: True` by default — `GET /api/public/files/{path}` returns 403 for private records; a per-file Private/Shared toggle enables the public link. Non-library uploads (logo, canvas images, chat/reply attachments) stay public and no longer appear in the library list (`in_library: True` filter) though they still count toward quota.
- Data portability: `GET /api/apps/{id}/data-export` streams a ZIP with `data/*.json` for every tenant collection (pages, CMS, leads, memberships, activity, workflows, analytics, people — password hashes stripped), all files under `files/` with a manifest, and a README. Button: "Download all data & media".
- Exports are now offline-capable: `bundle_media()` rewrites `/api/public/files/...` references in exported HTML/CSS to local `site/assets/<file>` binaries.
- Frontend: new Files tab (`/app/frontend/src/components/FilesPanel.jsx`) with multi-upload, search, thumbnails, copy link, download, rename, privacy toggle and delete. Agency-side only — nothing added to the client portal.
- Tested: iteration_25.json — backend 20/20 pytest, frontend 100%. Post-run fixes: clipboard promise now handled, library list filtered to `in_library`, delete is 404 on already-deleted, private-file gating added.
- Known: ingress can intermittently 502 on ~15 MB uploads / multi-MB export ZIPs (retry succeeds).

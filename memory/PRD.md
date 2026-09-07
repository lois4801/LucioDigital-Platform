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

## Backlog (P1/P2)
- P1: User adds ElevenLabs key (button in AI Media tab) — voice untested with a real key.
- P1: Move generated media (base64 in Mongo, fal temp URLs) to Emergent Object Storage.
- P2: Real CI/CD for mobile builds (currently MOCKED).
- P2: Team-level audit log CSV export; password reset email flow (Resend).
- P2: Stripe customer portal / cancel subscription; per-plan feature gating.
- Cosmetic: Radix Dialog aria-describedby warning; /auth/me 401 on public pages.

## Stripe notes
- Sandbox account CA (`acct_1UCqXZRU6y7XBGGy`), keys in backend/.env. Claim link shared with user in finish summary. Tax mode: Stripe-managed (full) with automatic fallback to calc-only.

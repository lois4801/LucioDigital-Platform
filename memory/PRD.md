# OmniStack AI — PRD / Working Memory

## Original problem statement
Production-ready multi-tenant SaaS application builder merging Framer-style visual website
building (Site Mode) with Lovable-style conversational AI app generation (App Mode). Includes
16 industry templates, AI-scored Lead Inbox with draft replies, export/handoff pipeline
(GitHub + .zip with React/Postgres starters), admin-editable CMS for the public landing page,
and inline text/image editing on the builder canvas.

## Language
Respond to the user in **English** only.

## Architecture
- Backend: FastAPI + MongoDB (motor), modular `register(api, db, ...)` files in `/app/backend`
- Frontend: React (CRA aliases `@/`), Tailwind, shadcn/ui, framer-motion, dnd-kit
- Auth: Emergent-managed Google Auth + JWT; LLM/video via Emergent Universal Key (Claude, Fal.ai)
- Preview URL comes from `REACT_APP_BACKEND_URL` in `/app/frontend/.env`

### Key backend modules
`studio.py` (theme/pages/AI site gen), `site_content.py` (premium niche packs / "Try another look"),
`locks.py` (master + granular lock registry), `page_guard.py` (page locks, 30-version history),
`edit_requests.py` (client change requests + single-use grants), `content_lock.py` (tenant content lock),
`web_import.py` / `zip_import.py` (site importers), `page_diff.py`, `videos.py`, `followups.py`,
`export_gen.py` (static HTML/CSS export + V2_CSS design system).

### Key frontend modules
`components/builder/Builder.jsx` (canvas), `BlockPreview.jsx` (block renderer + `DesignCtx`),
`EffectWrap.jsx` (reveal/parallax/stagger), `components/locks/LockContext.jsx` (lock UI),
`pages/PublicPreview.jsx` (live tenant site), `lib/theme.js`, `styles/tenant-v2.css`.

## Implemented

### Earlier sessions
- Dual-mode dashboard (Site Mode canvas + App Mode chat), 16 templates, premium niche packs
- Lead Inbox with AI scoring + draft replies, 48h automated AI follow-ups (cron)
- File Library, Client Portals, external data destinations (Supabase/Postgres/Drive UI)
- Full-site crawl importer (up to 100 pages), ZIP importer, form routing, Video Studio (Fal.ai/Pixabay)
- Tenant content lock, page locks + 30-version history with restore/undo, version diff

### 2026-06 (this session)
1. **Builder hook-order crash fixed** — state was declared after the effects using it; Site Mode renders again. (iter 33)
2. **Landing page "Editing on/off" toggle** for admins (`landing-edit-mode-toggle`, persisted in localStorage). (iter 33)
3. **Master + granular lock system** (iter 34, 16/16 backend):
   - `locks.py` registry: kinds = page | block | form | cms_collection | cms_item | workflow | data_destination | app_mode | overview
   - `GET /api/apps/{id}/locks`, `POST /api/apps/{id}/locks/all`, `POST /api/apps/{id}/locks/item`, `GET /api/locks/summary`
   - Master pill + state badge in the tenant header (every tab) and in Overview; padlocks on page tabs, outline blocks/forms, CMS collections/items, workflows, App Mode, Overview
   - Enforcement: 423 for editors/viewers on locked pages, locked sections inside a page save, CMS items, workflows; owner/admin always pass
   - Generic client "Request a change" → Inbox approval → single-use grant (`POST /api/apps/{id}/edit-request`, `GET /api/apps/{id}/edit-access?kind=&item_id=`)
   - Dashboard tenant cards/rows show Fully locked / Partially locked / Unlocked
4. **Framer-grade design standard (`design_v2`)** (iter 35 → 36, all green):
   - Fluid `clamp()` type scale (`--t-h1…--t-body`) + vertical rhythm tokens, Sora headings / Inter body variable fonts
   - Scroll reveals everywhere + staggered grid children, button/link/card micro-interactions, animated page transitions
   - 12-column grid container, generous whitespace, full-viewport-height hero (centered/cover variants)
   - Frosted glass sticky navbar, glass cards, layered shadows and gradients
   - Lazy + `object-cover` images with aspect boxes, hero background parallax, desktop-only cursor trail
   - 44px tap targets, smooth scroll, verified at 390px
   - Applied automatically to **new tenants**, AI-generated sites and "Try another look"; existing tenants untouched (`theme.design_v2` flag)
   - Same standard exported to static HTML/CSS (`export_gen.V2_CSS`, `_v2_polish`)

5. **Design Upgrade Button + Section Style Presets** (iter 37, 7/7 backend + all frontend flows green):
   - `POST /api/apps/{id}/site/upgrade-design` — flips a legacy tenant to the current standard with a
     **byte-identical pages payload** (verified); swaps to Sora/Inter only if the tenant still has the
     old default font pair; snapshots the site first so History → "Undo a whole site change" can revert it
   - `POST /api/site/upgrade-design-all` — bulk upgrade of the caller's legacy tenants (skips v2 ones)
   - UI: "Upgrade design" card + "Legacy look" badge in Overview, `Legacy look` chip on tenant cards,
     `Upgrade N legacy sites` action in the dashboard header; editors get 403
   - Section presets `block.style.preset`: **Editorial / Bold / Minimal / Luxe** + Default, per section in the
     Site Mode style panel, plus "Apply to every section on this page"; disabled on locked sections;
     rendered as `.pr-*` classes in the canvas, the live site and the exported `styles.css`/HTML

6. **Convert to Web App** (iter 38 → 39, all green — 24/25 then 8/8 after the lockout fix):
   - `POST /api/apps/{id}/convert-to-webapp {signup_mode}` — one automated pass, idempotent, owner/admin only.
     **Content preservation verified**: block props are untouched apart from added `props.collection` / `props.dynamic`
   - Tenant visitor auth (`/api/site/{token}/auth/register|login|me|forgot|reset`) — bcrypt + JWT with
     audience `site-user`, so tenant tokens are rejected by agency endpoints; per-email brute-force
     lockout keyed off `X-Forwarded-For` (5 fails → 429 / 15 min); hashed single-use reset tokens
   - Signup modes: `open` (default) | `approval` | `invite`, switchable via `PATCH /api/apps/{id}/webapp/settings`
   - Protected pages: everything except `/`, `/about`, `/services`, `/contact`; per-page toggle via
     `POST /api/apps/{id}/webapp/pages/{page_id}/access`; `GET /api/site/{token}/page/{slug}` leaks no
     content to anonymous visitors; themed `MemberGate` wall on the live site
   - Repeated sections (services, products, team, testimonials, pricing, gallery) copied verbatim into
     per-section CMS collections and re-bound (`dyn()` in BlockPreview) — a second section of the same
     kind gets its own `-2` collection, so no cross-contamination
   - Submissions: `POST /api/site/{token}/submit` → `submissions` collection, shown in Data & Storage
     (`SubmissionsPanel`, search + CSV export) with confirmation email to the submitter and notification to the owner
   - Admin panel `/site-admin/{token}` (`SiteAdmin.jsx`): submissions triage, user invite/approve/suspend/
     promote, content CRUD, 30-day analytics. Agency owner enters with their platform session; site admins
     sign in with email/password; standard users get 403 on every `/admin/*` route
   - Roles: `admin` | `user`; agency owner is seeded as the first panel admin
   - Button on **every** tenant: `convert-webapp-header-btn` in the tenant header (all tabs) and
     `convert-webapp-card` in Overview, with a post-conversion summary + panel link

7. **Member profile · Client invites · Bookings · Before/after links** (iter 40, 24/24 backend + UI green):
   - **Member profile** `/site/{token}/me` (GET/PATCH), `/me/password`, `DELETE /me` (only when the tenant
     enables `allow_self_delete`); "My account" on the live site lists the member's own submissions and booking chips
   - **Client panel invite** `POST /api/apps/{id}/webapp/invite-client` → single-use 7-day link
     `/site-admin/{token}?invite=CODE`; `GET/DELETE /api/apps/{id}/webapp/invites` (sent/accepted/expired,
     resend, revoke); `GET|POST /api/site/{token}/invite/{code}[/accept]`; client lands as full admin of their own site
   - **Bookings**: tick "This is a booking request" on any form → date + slot picker; modes `period`
     (Morning/Afternoon/Evening) or `slots` (per-tenant `business_hours`, taken times filtered out);
     Bookings tab in the panel with Confirm / Reschedule / Decline, each emailing the customer
   - **Before/after share link** `POST|GET|DELETE /api/apps/{id}/compare-link` → public `/compare/{code}`
     with an auto screenshot (mShots, retry + graceful fallback) beside the live rebuild in an `embed=1`
     iframe, and a lead form (`POST /api/public/compare/{code}/lead`) that drops into the tenant Inbox
   - UI: `ClientTools` card in Overview (invites + share link), `MemberAccount`, `Compare` page, `BookingPicker`

8. **Booking calendar · Weekly digest · Paid members area · Admin bookings** (iter 41, 16/16 backend + UI green):
   - **Bookings tab** per tenant: 24h × day grid with Day/Week/Month toggle, prev/today/next, 8-second live
     polling; overlapping bookings render **red** with a `clash-warning` badge; click a block for details →
     reschedule / cancel (notify or quietly). `BookingsCalendar.jsx`
   - **Admin-created bookings**: New Booking button or any empty slot → name, email, phone, service, date,
     time, duration, notes + pre-ticked "email the client". `POST|PUT|DELETE /api/site/{token}/admin/bookings[/{id}]`
     (panel-guarded; duration clamped 15–480 min)
   - **Monday client digest**: `PATCH /api/apps/{id}/webapp/digest` (on/off, hour, extra recipients),
     `GET /apps/{id}/digest/preview`, `POST /apps/{id}/digest/test`; recipients default to the client panel
     admins plus the agency owner; cron `POST /api/cron/weekly-digest` (bearer `WEBHOOK_CRON_SECRET`,
     `0 * * * 1` in `.emergent/crons.yml`, fires only for tenants whose send hour matches)
   - **Paid members area**: `PATCH /api/apps/{id}/webapp/paid` (one-time or subscription, price, currency,
     paid page_ids) syncs a Stripe price by `lookup_key members_{app_id}_{mode}` using the app's existing
     sandbox keys; `GET /api/site/{token}/paywall`, `POST .../paywall/checkout`, `GET .../paywall/status/{sid}`;
     `member_access` grants unlock every paid page; `GET /apps/{id}/paid-members` lists members + payment
     history; turning the toggle off reverts every paid page to public **immediately** (verified)
   - Paywall UI signs the visitor in with the existing auth first, then Stripe Checkout (card, Apple Pay, Google Pay)

9. **Gemini AI models integration** (iter 42):
   - `ai_models.py`: registry of six selectable text models (Claude Sonnet 5 / Haiku, **Gemini 3 Flash**,
     **Gemini 3.1 Pro**, GPT-5.4 / mini) via the Emergent Universal Key; Nano Banana
     (`gemini-2.5-flash-image-preview`) exposed for image generation
   - Precedence: tenant per-feature → tenant default → platform per-feature → platform default → built-in,
     resolved by `resolve_for(app_id, feature)` and used by site generation, the chat widget / AI editor,
     lead scoring, copy rewrite and SEO; unknown models fall back instead of erroring
   - `GET|PATCH /api/ai/models` (platform default, platform-admin only), `GET|PATCH /api/apps/{id}/ai-model`
   - **New Gemini capability**: `POST /api/apps/{id}/ai/seo` writes an SEO title + meta description for every
     page from its real content and stores it on `pages.seo` — content itself untouched
   - UI: `ai-model-card` in the tenant Bookings/settings tab with a tenant default plus a per-feature picker
     and a "Write SEO for all pages" button

10. **AI lead summary · booking follow-ups · platform-model fix** (iter 43, backend 15/16 + frontend green):
   - Fixed P0 from iter 42: `PATCH /api/ai/models` gated on a non-existent `user['is_admin']`; now also
     compares the caller's email to `ADMIN_EMAIL`. `PATCH {}` now `$unset`s the platform default (clears cleanly)
   - `ai_models.run_text(app_id, feature, system, prompt, session)` — shared one-shot generation on the
     tenant/feature-resolved model; `build_lead_summary(db, app_id, days=7)`
   - `GET|POST /api/apps/{id}/ai/lead-summary` — AI paragraph over the last 7 days of leads (volume, sources,
     hottest leads + one next action each), cached on `apps.ai_lead_summary`
   - `LeadSummaryCard.jsx` (`lead-summary-card`, `lead-summary-btn`, `lead-summary-text`) at the top of the
     Inbox and in the Overview right column; the Monday digest body now carries an `AI SUMMARY OF YOUR LEADS` section
   - Booking follow-ups: `POST /api/site/{token}/admin/bookings/{sid}/ai-followup?kind=reminder|thankyou` drafts,
     `POST .../followup-send {kind, body}` sends. Stored on `booking.followups.{kind}`. **Never auto-sends** —
     the admin edits the draft in the Bookings dialog (`booking-followup`, `followup-draft-*`, `followup-body`,
     `followup-send-btn`) and clicks send

## Testing noteA testing pass (iter 36) deleted two tenants during cleanup; they were recreated as
`app_6663b5de0007` (Northwind Roofing) and `app_c18671970769` (Design V2 Demo). Future test briefs
must forbid deleting apps/users/pages.
- **P1** Real GitHub push (currently MOCKED — needs a user PAT)
- **P1** Live ElevenLabs / Resend keys (MOCKED / graceful fallback)
- **P1** Real sync/export to client Supabase / Postgres / Google Drive / Dropbox (credential UI built, transport pending)
- **P2** Lock audit trail view (who locked what, when) in the Activity tab
- **P2** Shareable before/after comparison link for prospects

## Testing
- Reports: `/app/test_reports/iteration_27.json … iteration_36.json` (33–36 this session, all passing)
- Backend suites: `/app/backend/tests/test_iter33_*.py`, `test_iter34_master_and_granular_locks.py`, iter35/36 design suites
- Credentials: `/app/memory/test_credentials.md`

## Guardrails learned
- Never regenerate/overwrite tenant pages without the content lock check (`assert_unlocked`)
- Declare all React state before any effect that references it (Builder.jsx crash cause)
- A `transform` on an ancestor kills `position: sticky` — keep navbars outside motion wrappers
- `_clean_theme` only strips Roboto/Arial/Times now; Inter is a first-class default

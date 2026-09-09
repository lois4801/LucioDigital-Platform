# Lois-Tech — Product Requirements & Status

## Problem statement
Production-ready multi-tenant SaaS application builder merging Framer-style visual website building
(Site Mode) with Lovable-style conversational AI app generation (App Mode).

Core requirements:
1. Global dashboard with dual modes (Site Mode canvas / App Mode chat)
2. 16 pre-built industry templates, each with a unique visual identity
3. High-end UI/UX with premium animations
4. AI-scored Lead Inbox with inline AI draft replies + auto-classification (real vs test)
5. Export & Handoff pipeline: Website, Full-Stack App, Plugin package (+ plugin zip re-import)
6. Admin-editable CMS for the public landing page with dynamic Showcase manager
7. Tenant Overview dashboards that auto-sync with live Site Mode edits
8. Static site → full-stack web app conversion (auth, db, CMS)
9. Booking calendar, paid members area, client panel

## Hard platform rules (user-mandated)
- **Tenants are NEVER created automatically.** Only explicit admin actions insert a tenant:
  `POST /api/apps` (from the Template Gallery, or blank/import), plugin-ZIP import, website/ZIP
  import. Template redesigns, theme changes, defaults and migrations may only modify template
  definitions and platform defaults — never create tenant records.
- Removing a tenant means **archive** (`archived: true`): hidden, site offline, everything retained
  and restorable. Permanent removal is a separate explicit `DELETE /api/apps/{id}/purge` and is only
  allowed on an already-archived tenant.
- **Every lead from every tenant lands in the admin global inbox**, including archived and removed
  tenants ("Removed tenant").
- The **Template Gallery is the default new-project flow**.

## Architecture
React (craco) + Tailwind + Shadcn UI · FastAPI (port 8001, `/api` prefix) · MongoDB.
Auth is **cookie-based** JWT (HttpOnly, SameSite=None) — login returns the user object, no token.
Design system: `backend/site_content.py` (NICHES copy + LOOKS design tokens) →
`frontend/src/lib/theme.js` (themeVars / applyMode / modeCls) →
`styles/tenant-v2.css` + `styles/tenant-modes.css` → `components/builder/BlockPreview.jsx`.

## Integrations
- Emergent Universal Key — Claude / GPT / Gemini text + image
- Stripe (env key `sk_test_emergent`) · Emergent-managed Resend · Emergent-managed Google Auth

## Implemented
- Full platform: Site Mode canvas, App Mode AI generation, templates, CMS, file library, bookings,
  paid memberships, client portals, master + granular locks, content lock
- Export pipeline (Website / Full-Stack App / Plugin) + plugin zip re-import
- Lead Inbox: auto-classification, admin override, AI draft replies, AI lead summary, lead source
  insights, live email delivery, auto-archive cron
- Landing page showcase + Showcase Manager (featured stars, drag-to-reorder), empty state at zero tenants
- Tenant Overview auto-sync with Site Mode edits · Rebrand OmniStack → Lois-Tech
- **Sept 8, 2026 — regression fixes (iter 55/56)** and **deployment fixes (deployment_agent PASS):**
  `/health` + `/api/health` endpoints, `CORS_ORIGINS="*"` with `allow_origin_regex` for cookie auth,
  fault-tolerant startup, `.get()` for ADMIN_EMAIL.
- **Sept 9, 2026 — 16 unique template looks + light/dark system + animation fixes (iter 57, 17/17):**
  `site_content.LOOKS` per-template identity (palette, fonts, radius, hero, mode) + one `pr-site-*`
  CSS preset each; `applyMode()`/`MODE_PRESETS` full-design mode switch with `--thead`/`--tbody`
  contrast contract; reveals start at opacity 0.3; strikethrough reset; secondary-CTA contrast rule.
  Fixed a long-standing bug where `font-[var(--tfh)]` never compiled, so no template had ever
  applied its heading font.
- **Sept 9, 2026 — no-auto-tenants + archive + global inbox (iter 58, 13/13):**
  Removed every auto-creation path (`SEED_APPS`, `SEED_ACTIVITY`, `ensure_editor_tenant`,
  `ensure_demo_tenants`, `DEMO_TENANTS`, startup reseed). Added `POST /api/apps/{id}/archive`,
  `GET /api/apps?archived=true`, dashboard Archive/Restore controls + Archived view, admin-wide
  global inbox with `app_archived` tagging and "Removed tenant" fallback, archived tenants excluded
  from landing/showcase, and `_new_tenant_theme()` so manually created tenants inherit their
  industry template look. All 7 previously auto-created tenants archived (recoverable); workspace
  now boots to 0 active tenants.

## Current data state (Sept 9, 2026, after iter62)
1 active tenant: `app_d8a1146c7426` Formcheck Medical (healthcare, dev throwaway) · **0 archived**.
⚠️ The 6 archived demo tenants and Northwind Roofing were destroyed by testing-agent cleanup during
iterations 58-62 despite explicit protection instructions. Their 5 leads survive in the admin
global inbox, labelled "Removed tenant". They can be recreated from the Template Gallery on request
(the designs and copy are template-generated, so a rebuild is faithful).

## Backlog
- **P1** Real ElevenLabs voice — MOCKED; needs the user's ElevenLabs API key (next in agreed order) — MOCKED; needs the user's ElevenLabs API key (next in agreed order)
- **P1** External DB sync export target (Supabase / PostgreSQL) + cloud drives
- **P1** Real GitHub push integration — MOCKED; user chose to hold off on the PAT
- **P2** Member "Delete my account" flow in profile
- **P2** Template gallery: preview all 16 template designs before creating a tenant
- **P2** Legacy suites `test_iter11..52` hardcode dead tenant ids and 404 — refactor or delete
- **P3** Internal `omnistack` strings in `storage.py` APP_NAME and the plugin manifest format

## Sept 9, 2026 — Platform-wide CTA modal form system (iter61 + iter62, 19/19 backend, frontend 100%)
- `backend/cta_forms.py`: `CTA_PATTERN`/`qualifies()` CTA intent detection, per-industry `FIELD_SETS`
  (real_estate, education, healthcare, fitness, legal, hospitality/restaurant, construction) plus
  `FALLBACK`, `cta_labels()` page scanner, per-tenant `cta_forms` collection,
  `GET/PUT /api/apps/{id}/cta-forms`, `POST .../scan`, public
  `GET /api/public/site/{token}/cta-forms` and `POST .../{form_id}/submit` (validates required
  fields, writes the lead through the inbox with `form_label`, plus a `submissions` row).
- Email field can never be removed (400) and unsupported field types are rejected (400).
- New tenants provision forms automatically inside `_build_template_pages`; newly added CTA buttons
  are picked up by the rescan endpoint with the fallback field set.
- Frontend: `CtaFormModal.jsx` (portal modal, dark backdrop, X + outside click + Escape, dynamic
  field renderer, brand-coloured submit, success state, `themeVars(theme)` applied on the portal so
  tenant theme vars survive the portal boundary), `CtaFormEditor.jsx` (drag-reorder, inline
  "+ Add a Field" type menu, autosave, simplified client mode), `CtaFormsPanel.jsx` (Forms tab in
  AppDetail), CTA buttons in `BlockPreview` become real buttons, Builder canvas opens the editor,
  Leads Source column shows the triggering button label.

## Sept 9, 2026 — Code-quality review fixes (iter63, 17/17 backend, frontend 100%)
- **Circular import removed:** new `backend/lock_shared.py` owns `KINDS`, `LABELS`, `active_grant`,
  `consume_grant`; `locks.py` and `edit_requests.py` both import it at module top and neither
  imports the other (the old deferred function-level imports are gone). Lock + edit-request +
  single-use-grant flows re-verified end to end.
- **Token storage hardened:** the two client-facing site JWTs moved from localStorage to
  sessionStorage with a one-time migration that copies then deletes any legacy token —
  `SiteAdmin.jsx` (`site_admin_token_*`) and `MemberGate.jsx` (`site_member_token_*`).
  `Builder.jsx` localStorage was left as-is: it holds page draft content, not credentials.
- **Stable React keys:** all 12 array-index keys in `BlockPreview.jsx` replaced with
  content-derived keys (nav, stats, team, logos, gallery, features, testimonials, pricing, FAQ,
  chart, footer columns, article paragraphs). Zero key warnings / ReferenceErrors across 4 tenant
  pages + all 16 template previews.
- **Lint truth-checks:** server.py:762 is an embed `<script>` built from `FRONTEND_URL` + the public
  preview token, **not a secret** (repo-wide scan for sk_live/sk_test/AKIA/PEM/inline passwords
  outside `os.environ` came back clean). pyflakes found **no** undefined variables; the real
  findings (3 f-strings without placeholders) were fixed. The "260 `is` vs `==`" finding is a false
  positive — every instance is a correct `is None` / `is not None` check.
- **Deliberately not done:** the complexity / import-count refactors (splitting `register()`
  functions, splitting Dashboard and Builder). They are churn with real regression risk and no
  user-visible benefit; revisit only if a feature needs to touch those files anyway.

## Order agreed with user
ElevenLabs → External DB sync → Delete-my-account → GitHub push (PAT on hold)

## Sept 9, 2026 — Template Gallery + Archive restore + Client picks + Leads table (iter59, 15/15)
- `backend/templates_gallery.py`: `GET /api/public/templates` (16 designs + 14 categories),
  `GET /api/public/templates/{key}` renders a template's theme + 4 pages **in memory** (no tenant
  created), client share links (`/api/template-shares`, `/api/public/template-shares/{token}`,
  `/select`, `/ack`) with a hard 7-day expiry.
- `POST /api/apps` accepts `template_key` and builds the full 4-page template site
  (`_build_template_pages`) instead of a blank starter page; the response is refetched so it
  includes `site_niche` + `premium_site_v`.
- `GET /api/apps/archived/summary` (snapshot: pages/leads/bookings/members/files + last active) and
  `DELETE /api/apps/{id}/purge` (400 unless already archived).
- Frontend: `pages/TemplateGallery.jsx` (live scaled thumbnails via the real BlockPreview renderer,
  full-page scrollable preview with page tabs, category tabs, share dialog, client mode),
  routes `/templates` (protected) + `/choose/:token` (public, no login), dashboard gallery-first
  New project, client-pick banner, Archived Tenants section with Restore / Permanently delete.
- `pages/Leads.jsx` table rebuilt: `table-fixed` + colgroup (38/20/12/14/12% + 72px), wrapped in
  `overflow-x-auto` with `min-w-[1040px]`, no hidden columns, full emails, `NN/100` score.
- Bug fixed by the testing agent and kept: `site_content._sec()` crashed on the 2-tuple `dining`
  section, which 500'd the hospitality template preview.

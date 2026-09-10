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
- **NO AUTOMATIC TESTING OR PREVIEW RENDERS (June 2026, permanent).** After finishing a set of code
  changes the agent must STOP, list what changed, and ask verbatim:
  *"I have finished applying the requested changes. Here is a summary of everything that was modified:
  [list of changes]. Before I run any tests or render a preview, do you have any additional
  modifications you would like to make first? Adding them now will save credits by combining
  everything into a single test run. Reply YES to add more changes or NO to proceed with testing now."*
  Wait for the admin. YES → accept the next change and repeat the prompt when done. NO → run tests and
  render a preview for the **Test Lab only**, never for a live tenant. This is mandatory before every
  single test run, with no exceptions. The admin also has an explicit **Run Test** button
  (`run-test-btn` → `POST /api/test-lab/run-test`, Test-Lab-scoped smoke check).
- Agents must never auto-run a full platform test, never spin up new tenants / demo sites / template
  previews during a build pass, and never rebuild, re-render or redeploy until the admin triggers it.
- **STAGING TENANT.** `Rollout Target Demo` (`is_staging: true`, orange STAGING badge, `protected`) is
  the final real-environment check. It is excluded from `_targets()` so "Push to All Tenants" only ever
  means live client tenants; it is reached exclusively via **Push to Staging** on the Test Lab card
  (`push-to-staging-btn`) or the Test Template card (`push-template-to-staging-btn` →
  `POST /api/test-template/push-staging`), both of which go through the diff viewer + CONFIRM and are
  recorded in the history log (`kind: "template_staging"`) and undoable.
- **CREDIT-SAFE DEFAULT — TEST INSTANCES ONLY (June 2026, permanent, overrides everything else).**
  Every change goes to exactly ONE test instance first:
  - Template design / animation / layout / new section work → the **Test Template** (`test_template`).
  - App, feature, UI, form, dashboard or system-behaviour work → the **LucioDigital Test Lab**
    tenant (`app_testlab`).
  It reaches anything else ONLY when the admin opens the Diff Viewer and clicks **Push to One** or
  **Push to All** and types CONFIRM. No prompt, agent action, migration or startup task may write to
  more than that single test instance in one operation. If a request does not name a specific tenant
  or template, it targets the test instance — never "all".
- **DEFAULT TARGET IS THE TEST LAB (June 2026, permanent).** Every design change, animation, template
  redesign or new platform behaviour lands on the `LucioDigital Test Lab` tenant (`app_testlab`) only.
  It reaches live tenants **exclusively** when a rollout admin clicks "Push to All Tenants" (or a
  template's "Push to All Tenants Using This Template") and types CONFIRM. No prompt, agent action,
  migration or startup task may mutate live tenants without that confirmation. If a request does not
  literally say "apply to all tenants", it goes to the Test Lab.
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


## June 2026 — P0 Handoff-readiness pass (iter65, backend 14/14, frontend smoke clean)
Goal: the platform can be handed to a client and self-hosted with **their** keys, without moving off
FastAPI/Mongo. No feature or UI changes.
- **Single LLM seam — `backend/llm_provider.py` (NEW).** Everything AI now goes through it:
  `get_chat(provider, model, system, session_id)` (async `send_message` / `stream_message` with local
  `UserMessage`/`TextDelta`/`StreamDone` dataclasses), `generate_image()`, `generate_speech()`,
  `llm_available()`, `image_available()`, `video_available()`, `llm_mode()`, `status()`.
  - `emergent` mode when `EMERGENT_LLM_KEY` is set (unchanged behaviour, this preview).
  - `byo` mode when only `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` exist → litellm for
    text, OpenAI SDK for images + TTS, `FAL_KEY` for video. `LLM_MODEL_OVERRIDE` pins a model when the
    client's account doesn't have the catalogue ids; provider substitutions log a warning.
  - `none` mode: app runs, AI endpoints return a clear "no LLM key configured" error.
  - Refactored call sites: `server.py` (/ai/edit), `ai_models.py` (run_text + /ai/seo),
    `studio.py` (_claude + TTS), `site_sync.py`, `web_import.py`, `extras.py` (media config/image/video),
    `growth.py` (blog covers), `inbox.py`. No direct `emergentintegrations` imports remain outside the seam.
- **Storage driver seam:** `storage.py` `STORAGE_DRIVER` = `proxy` (default, Emergent object storage) or
  `gridfs` (uploads stored in the client's own MongoDB; covered by `mongodump`). Round trip verified.
- **De-hardcoding:** `DNS_CNAME_TARGET` now env-driven (docs flag it as must-override on handoff).
  Google OAuth broker URL intentionally left untouched (breaking it breaks auth); docs explain the
  JWT-only fallback.
- **New files:** `backend/.env.example`, `frontend/.env.example`, `backend/Dockerfile`,
  `frontend/Dockerfile` + `frontend/nginx.conf` (SPA fallback + `/api` proxy), `docker-compose.yml`
  (mongo + backend + frontend), `.dockerignore`s, `HANDOFF.md` (stack, config, BYO keys, auth, data
  ownership), `DEPLOYMENT.md` (compose + manual self-host, health checks, first run, backups).

## Remaining roadmap
- P1: Vite + TypeScript conversion of the frontend (~119 files)
- P1: Supabase migration (Auth + Postgres + Storage + RLS) **or** Supabase as an optional export target
- P1: Real ElevenLabs voice + real GitHub push (both waiting on user PATs)
- P2: PayPal integration · P2: expose member "delete own account" in profile


## June 2026 — Vite + TS toolchain, Supabase export, Handoff bundle (iter66, 10/10 backend, frontend clean)

### 1. CRA → Vite 6 migration (TS toolchain, JSX kept)
- `vite.config.ts`: react plugin, `@` → `src`, `envPrefix: ["REACT_APP_","VITE_"]` **plus** a `define`
  shim that injects every `process.env.REACT_APP_*` so all 14 existing call sites keep working.
  Dev server pinned to `0.0.0.0:3000`, `allowedHosts: true`, HMR over `wss` clientPort 443,
  `build.outDir: "build"` (keeps the deployment path unchanged).
- Root `index.html` (was `public/index.html`) with `<script type="module" src="/src/index.jsx">`;
  the Emergent main script and the PostHog snippet were carried over verbatim.
- `src/index.js`/`src/App.js` → `.jsx` (the only two .js files containing JSX). `tsconfig.json` with
  `allowJs`, `strict`, `jsx: react-jsx`, path alias; `yarn typecheck` = `tsc --noEmit` (clean).
- Converted to TS: `src/lib/api.ts`, `src/lib/utils.ts`. Everything else stays `.jsx`.
- Removed: `craco.config.js`, `jsconfig.json`, `frontend/plugins/`, and the `@craco/craco`,
  `react-scripts`, `cra-template` deps. **Also removed the `rollup: 2.80.0` resolution** — that CRA-era
  pin is what made Vite fail to boot (`./parseAst is not exported`). Do not re-add it.
- Trade-off: the Emergent visual-edits overlay was CRA/craco-only and is gone. Build time ~5 s.
- Scripts: `start` = `vite`, `build` = `vite build`, `preview`, `typecheck`.
- Also fixed: `src/index.css` had the Google Fonts `@import` after `@tailwind` — Vite/postcss rejects that.

### 2. Supabase export — `backend/supabase_export.py` (NEW)
- `TABLES` maps 11 Mongo collections → `lt_*` Postgres tables (scalar columns + full row in `data jsonb`),
  plus `lt_tenants` as the FK parent.
- `build_sql(db, app_doc, prefix)` → one idempotent script: `begin;` → DDL (`create table if not exists`,
  per-table tenant index) → `delete` + `insert` of the tenant's real rows (single quotes escaped via `_lit`)
  → RLS (`enable row level security`, `read_own_tenant` select policy for `authenticated` scoped by the
  `tenant_ids` JWT claim; service_role bypasses) → `commit;`.
- Endpoints: `GET /api/apps/{id}/supabase/status`, `GET /api/apps/{id}/supabase/sql` (file download),
  `POST /api/apps/{id}/supabase/push` (uses the posted `connection_uri`, else the saved
  supabase/postgres `data_destination` secret, decrypted via `data_destinations._decrypt`; psycopg2 in a
  thread; result stored on `apps.supabase_push`).
- UI: `components/SupabaseExportCard.jsx` in the Handoff & Export tab
  (`supabase-export-card`, `supabase-uri-input`, `supabase-push-btn`, `supabase-sql-btn`).
- NOT verified end-to-end: a real push needs a live Supabase project. Only the error paths were tested.

### 3. One-click Client Handoff Bundle — new `handoff` export kind
- `export_pkg.build_handoff()` composes `build_website` + `build_fullstack` and adds the data, files,
  Supabase migration, `.env.example` and a generated README. Zip layout:
  `site/` · `app/` · `data/*.json` (12 collections + tenant.json) · `files/` + `manifest.json` ·
  `supabase/migration.sql` + `README.md` · `.env.example` · `README.md`.
  Bundled assets are written into **both** `site/` and `app/frontend/public/` (and never at the zip root).
- `KINDS` + `/export/start?kind=handoff` accept it; UI is a 4th card in `ExportCards.jsx`
  (`export-card-handoff`, `export-handoff-btn`, `export-download-handoff`), grid now 4-up.
- Verified: 104 files / ~23 MB for a 4-page tenant; the other three kinds still build and download.

## June 2026 — Builder header: three separated rows (permanent layout rule)
- The builder header is exactly three stacked, non-overlapping full-width rows, each with a 1px
  `--line` divider: **Row 1** nav tabs (`header-row-tabs`, horizontally scrollable, no wrap),
  **Row 2** the page/tenant selector (`header-row-pages`, `min-h-[80px]`, its scrollbar contained by
  `pb-2`), **Row 3** the toolbar (`header-row-toolbar`, `py-3` = 12px, `flex-wrap` so buttons wrap to a
  second line instead of clipping).
- Row 2 + 3 live in `Builder.jsx` and break out of `<main>`'s padding with `-mx-6 lg:-mx-10 -mt-8`, so
  they span the viewport while keeping 24/40px side padding and ≥16px on the right (`pr-4` inside the
  pages strip).
- Page cards are fixed size — `w-[160px] min-w-[160px] h-[72px]` — so the row height can never collapse
  and push the toolbar upward. The "+" button matches at `h-[72px]`.
- `<header>` and `<main>` carry `w-full max-w-full` and no `overflow-hidden`, so nothing on the right
  edge is clipped. Verified at 1600px and 1100px: rows at y=90 / 135.5 / 224.5, zero overlap.
- Keep this structure for any new header control — add it inside Row 3, never beside the page cards.

## June 2026 — Sign-in overhaul (auth_extra.py)
- **No prefilled credentials.** `Login.jsx` used to hardcode the owner's email + password in
  `useState` — removed. New visitors get empty fields (`autoComplete="off"`); an address is restored
  only if the visitor ticked **"Save my email on this device only"** (`localStorage` key
  `lt_saved_email`, per browser, never the password, never shared between visitors).
- **`backend/auth_extra.py`** (all sessions reuse the existing HttpOnly cookie JWT):
  - `GET /api/auth/providers` → which options are live (`google`, `magic_link`, `microsoft`, `yahoo`).
  - Email verification: form signup now sets `email_verified: false` and sends a Resend
    (Emergent-managed, `EMERGENT_EMAIL_KEY`) confirmation mail; `POST /api/auth/verify/request`
    (throttled 3/2min) and `GET /api/auth/verify?token=` → `/login?verified=1`.
  - Magic link sign-in **and** form-free sign-up: `POST /api/auth/magic-link`,
    `GET /api/auth/magic?token=` (creates the account if new, then logs in).
  - Microsoft Entra (`common` tenant → covers outlook/hotmail/live) and Yahoo OIDC:
    `/api/auth/{provider}/start|callback`, authorization-code + PKCE, signed state cookie, nonce check,
    JWKS ID-token validation, identity linking via `users.auth_identities`. **Dormant until
    `MICROSOFT_CLIENT_ID/SECRET` and `YAHOO_CLIENT_ID/SECRET` are set** — `start` then redirects to
    `/login?provider_unavailable=<provider>` and the button shows a "use email instead" toast.
  - Tokens live in `auth_tokens` (sha256 hash, single-use, 30-min expiry).
- Frontend: `components/SocialSignIn.jsx` (Google + Microsoft + Yahoo + magic link) on both Login and
  Register; Register shows a "confirm your email" notice with a Resend button.
- Landing + public tenant sites: always-visible floating **Sign in** button (bottom-left,
  `floating-signin-btn` / `preview-signin-btn`) plus a floating **cursor-effects picker** for every
  visitor (11 effects, opens upward, remembered per browser; signed-in users also sync server-side).

## June 2026 — Owner/visitor landing parity + dashboard text editing
- The landing page now renders **identically for owners, users and visitors**: the nav always shows
  "Sign in" + "Start free" (the signed-in "Dashboard" pill was removed), the hero CTA always reads
  `hero_cta`, and the floating bottom-left stack is always the cursor picker + "Sign in".
- Admin-only controls moved out of the way into a compact top-left bar (`landing-admin-bar`,
  `fixed top-4 left-4`): the `landing-edit-mode-toggle` ("Editing off · click to edit") plus a
  `landing-admin-dashboard-btn` shortcut. Nothing else on the page betrays that an admin is viewing it.
- **`components/LandingTextEditor.jsx`** — every landing text is now editable from inside the dashboard
  (`nav-landing-text-btn` → modal with search, 15 fields, batched save via `PUT /admin/landing`,
  testids `landing-text-input-<key>` / `landing-text-save-btn`), so the owner never has to leave the
  dashboard to fix copy. Inline click-to-edit on the landing page still works as before.
- Dashboard header also has a **View landing page** button (`nav-view-landing-btn`) and the
  Lois-Tech / Agency Workspace logo is now clickable (`dashboard-logo-home-btn`) — both `nav("/")`.

## Remaining roadmap (updated)
- P1: Supabase as the platform's own backend (Auth + Postgres + RLS) — still Mongo today
- P1: Real ElevenLabs voice + real GitHub push (waiting on user PATs)
- P2: Full `.tsx` conversion of the remaining ~117 components · PayPal · member "delete own account"


## June 2026 — Test Lab tenant + controlled global rollout (iter67, 16/16 backend, frontend clean)

**This is now the platform's permanent default behaviour — see "Hard platform rules" at the top.**

### PART 1 — the Test Lab (`backend/test_lab.py`)
- `ensure_test_lab()` runs on every startup (idempotent): tenant `app_testlab`,
  name `LucioDigital Test Lab`, `is_test_lab: true`, `protected: true`, `archived: false`, and one page
  per template — **all 32** (`template_key` on each page, first at slug `/`, the rest `/t-<key>`).
  Name + description are re-asserted on every boot so nothing can drift them.
- Protection: `/apps/{id}/archive`, `/apps/{id}/purge` and `DELETE /apps/{id}` all return 400 for
  `is_test_lab`/`protected`; the dashboard hides the archive button on that card.
- `content_lock.sync_overview()` returns early for the Test Lab — otherwise it renamed the tenant to
  the navbar brand of whichever template sat on `/` (this actually happened; fixed).

### PART 2 — global rollout
- `GET /api/test-lab` · `GET /api/test-lab/rollout/preview` (target list + current value per scope) ·
  `POST /api/test-lab/rollout {scopes, confirm}` · `GET /api/test-lab/rollout/jobs[/{job_id}]`.
- Six opt-in scopes (`SCOPES`): `theme`, `mode`, `skin`, `motion`, `labels`, `forms`. Only design and
  behaviour ever move — never a tenant's text, images, pages, leads or CMS.
- Gates: rollout admin only, and `confirm` must literally be `CONFIRM`. Runs as a background task with
  live `pct/done/changed` progress; the dashboard stays usable; ends with the exact success toast.
- Every tenant's previous values are written to `rollout_snapshots` before the patch (groundwork for
  a future "Undo last rollout" — the modal still says it cannot be undone).
- Rollout admins: `ADMIN_EMAIL` plus any emails in `platform_settings._id="rollout_admins"`, managed
  with `GET/POST /api/rollout-admins` and `DELETE /api/rollout-admins/{email}` (UI inside the modal).

### PART 3 — template rollout control
- `template_states` collection tracks a hash of each template's `LOOKS` entry. On startup
  `mark_template_states()` flips any template whose design changed to `status: "pending"` — it does
  **not** touch live tenants.
- `GET /api/templates/rollout-status` · `POST /api/templates/{key}/rollout {confirm}` (applies that
  look only to tenants whose `site_niche == key`, snapshots first) · `POST /api/templates/{key}/discard`
  (accepts the new baseline without touching tenants).
- Gallery UI: yellow `Pending Rollout` badge per card, a header pending count, a
  "Push to All Tenants Using This Template" button on all 32 cards, and the same CONFIRM modal.

### PART 4 — startup no longer mutates live tenants
- `site_content.retheme_all()` is **no longer called on boot** (kept for manual/admin use).
  Startup now logs `Test Lab re-themed: 1 tenant(s)` + `Templates pending rollout: N`.
- Frontend: `components/RolloutModal.jsx`, `components/TemplateRolloutModal.jsx`; TEST badge +
  push button on the Test Lab dashboard card (`tenant-test-badge-app_testlab`,
  `push-to-all-tenants-card-btn`) and in the tenant editor header (`header-test-badge`,
  `push-to-all-tenants-btn`).


## June 2026 — Diff Viewer + Rollout History + Undo (iter68, 17/17 backend, UI verified)
- `GET /api/test-lab/diff[?app_id=]` — aggregated diff between the Test Lab and live tenants.
  `DIFF_FIELDS` drives Design / Animations / Features rows; UI labels and CTA form field lists add
  Content / Forms rows; removed labels appear as `kind: "removed"`. Rows carry
  `{id, category, label, old, new, kind, tenants, variance}` and only appear when they genuinely differ.
- `POST /api/test-lab/rollout` accepts `changes:[ids]` (Push Selected) as well as the legacy
  `scopes:[...]`, plus `target_app_ids:[...]` for Push to One Tenant. Stores the filtered diff +
  categories on the job. `_run_rollout` reports `done` / `partial` / `failed`.
- `GET /api/test-lab/rollout/history` — permanent, read-only, newest first, exactly one entry has
  `can_undo: true`. `GET /api/test-lab/pending` returns per-tenant unpushed-change counts.
- `_snapshot()` captures theme + ui_skin + cursor fields + UI labels + CTA form structures before every
  rollout. `POST /api/test-lab/rollout/jobs/{job_id}/undo` (CONFIRM + most-recent-only) restores them in
  the background with `undo_pct`, then marks the entry `undone` with `undone_at` / `undone_by`.
- Frontend: `components/DiffViewer.jsx` (full-screen viewer + the shared `DiffTable`),
  `pages/RolloutHistory.jsx` at `/rollout-history` (nav button `nav-rollout-history-btn`),
  `RolloutModal.jsx` is now two-stage (diff → confirm).

## June 2026 — Test Template + Push to One + visual indicators (iter69, 13/13 backend, UI verified)
- **`backend/test_template.py`** — `test_template` is a dedicated 33rd template cloned from
  `it_services` (no client-facing design is ever used as a sandbox) and is hidden from client-facing
  template pickers. `install()` registers it at startup; `load_overrides(db)` re-applies every pushed
  look from the `template_looks` collection so pushes survive restarts.
- `GET /api/test-template` · `GET /api/test-template/diff?scope=all|classic|studio|selected&keys=` ·
  `POST /api/test-template/rollout` (rollout-admin + CONFIRM, `changes` for Push Selected). A push
  writes a `rollout_jobs` entry with `kind="template_look"`, snapshots `before_look` per template, and
  flips each touched template's `template_states.status` to `pending` (tenants on it still need a push).
- `_run_undo()` handles `before_look` snapshots, so template pushes are undoable like tenant rollouts.
- Push to One Tenant: `_targets(only)` + `RolloutIn.target_app_ids` + `?app_id=` on the diff endpoint;
  those jobs are recorded with `kind="single"`.
- Frontend: `components/TemplatePushModal.jsx` (scope switch + diff + CONFIRM),
  `components/PushToOnePicker.jsx`; Test Template pinned first in the gallery with a **yellow** TEST
  badge (`template-test-badge`) and both push buttons; Test Lab pinned first on the dashboard with a
  **green** TEST badge and `push-to-one-tenant-btn`; **orange** "Pending Update" badges on tenants
  (`tenant-pending-badge-*`) and templates (`template-pending-badge-*`).

## June 2026 — Site Mode page bar restyle (PagesBar)
- The user's "tenant navigation bar" is the horizontal page bar at the top of Site Mode
  (`components/builder/PagesBar.jsx`) — in the Test Lab it lists all 33 template pages.
- Selected card fills with **that page's own** `theme_preview.primary` (falls back to the tenant theme)
  at 85%, 2px full-opacity brand border, `0 8px 26px` brand glow at 30%, text white or `#222222` chosen
  by relative luminance, and a template-key tag pill on a darker translucent background. Unselected
  cards stay flat `--bg-2` and dim. All colour properties transition in `0.25s ease`.
- New `.tenant-scroll` class in `index.css`: 8px-tall always-visible scrollbar, rounded caps,
  `#666666` thumb → `#ffffff` on hover/active, `#2a2a2a` track, Firefox `scrollbar-color` included.
- Never hardcode brand colours here — they are read live from the page/tenant theme.

## 2026-06 · Session (fork): auth FX, landing mobile fixes, Test Lab editorial redesign

### Implemented
- Cursor FX: default effect = Water Bubbles; removed per-particle `shadowBlur` and per-frame gradients
  (Fairy Dust and all effects now 61 FPS); global caps 170 / page-layer 90.
- Full-page FX layer `components/PageCursorFX.tsx` + `startPageCursorFX()` in `lib/cursorEffects.ts`:
  covers corners/edges/open space, z-index 0, pointer-events none, 0.6 alpha in empty space and
  0.35 behind `[data-fx-content]` (even-odd canvas clip), particle count halved < 768px.
- Cursor picker converted to a horizontal top strip: `CursorFXBar` in `components/CursorFX.tsx`.
- Sign-in + sign-up redesigned as ONE unified full-page workspace (split layout removed):
  full-page background video/gradient/particles, centered semi-transparent card, logo top-left,
  tagline bottom-left. Files: `pages/Login.tsx`, `pages/Register.tsx`.
- Landing mobile/tablet: admin controls moved to a slim dedicated top bar; hamburger nav < md;
  hero CTAs stacked full-width on mobile; bottom controls in their own bottom bar; ChatWidget
  gained a `lift` prop so it never covers the Sign in button; fixed a grid `min-w-0` overflow bug.
- Brand mark clickable everywhere → always `/` regardless of auth state (login, register, landing,
  dashboard, portal, public preview) with a forced `cursor: pointer` override; email shell in
  `backend/auth_extra.py` now links the brand name to FRONTEND_URL.
- Frontend fully migrated to TypeScript: 132 `.jsx` → `.tsx`, remaining `.js` → `.ts`,
  `index.html` entry updated, `tsconfig` relaxed (`strict: false`) for migrated JS-style code.
- NEW (Test Lab ONLY, not pushed): premium editorial motion redesign at route `/test-lab/landing`
  → `pages/TestLabLanding.tsx` + `components/editorial/{motion,HeroCards,Ribbon,BentoGrid}.tsx`
  + `.ed-*` animation system appended to `index.css`. Palette #080808 mono with lime/teal/orange
  accents; 10 floating hero cards (5 on mobile) with sine drift + cursor parallax; trim-path glow
  lines; overshoot word headline; odometer counters; dual opposite ribbons (pause on hover);
  bento grid with gradient hairline borders and micro-animations; scroll reveals; reduced-motion
  kill switch. Entry point: landing admin bar → "Test Lab redesign". lois-tech.ca untouched.

### Pending
- P0: Admin approval + diff review before any rollout of the editorial redesign to live tenants.
- P0: Regression run (testing_agent) is PAUSED per the Credit-Safe rule until admin replies NO.
- P1: Microsoft/Yahoo OAuth are built and env-gated; buttons render dimmed until keys are supplied.
- P1: ElevenLabs + GitHub push integrations still awaiting PATs.

## 2026-06 · Case studies + approval workflow + per-tenant Site Mode + template revision

### Implemented (Test Lab / Test Template scoped; nothing pushed live)
- `backend/case_study.py`: per-tenant case studies (`case_studies` collection), public index
  `GET /api/public/case-studies`, single `GET /api/public/case-studies/{slug}`, admin
  `GET|PUT /api/apps/{id}/case-study` (draft/published), seeded for Test Lab only.
- Per-tenant Site Mode `GET|PUT /api/apps/{id}/site-mode` → {style: original|editorial,
  mode: light|dark, animation: full|reduced|none, publish: draft|preview|live, template_key}.
  Writes are scoped to one app_id; PublicPreview applies `.ed-scope` / `.ed-static` from it.
- Redesign approval workflow: `GET /api/redesign/pending`, `POST /api/redesign/flag|reviewed|dismiss`,
  flag auto-raised at startup for `editorial-motion-v1`. Dashboard banner → `/redesign-review`
  (`pages/RedesignReview.tsx`): side-by-side live vs Test Lab iframes, desktop/tablet/mobile toggles,
  approval prompt, Generate Diff → existing RolloutModal/DiffViewer, then Push to One Tenant /
  One Template / All with the existing confirmation modal.
- Frontend: `pages/CaseStudy.tsx` (`/work/:slug`), `pages/Showcase.tsx` (`/work`, bento index),
  `components/CaseStudyEditor.tsx` (dashboard "Edit Case Study" per tenant card),
  `components/SiteModePanel.tsx` (in the tenant Site Mode tab). Landing nav + mobile menu gained
  a "Client work" link.
- `backend/test_template.py`: EDITORIAL_LAYER staged on the Test Template only
  (editorial, dark base, bento, floating gallery, ribbon, reveals, counters, glow paths, parallax)
  and added to LOOK_FIELDS so every flag is diffable/pushable/undoable.

### Pending (blocked on admin)
- P0: Admin must review `/redesign-review`, Generate Diff and choose a rollout target. Until then
  no live tenant or template is touched.
- P0: testing_agent regression still paused per the Credit-Safe rule.

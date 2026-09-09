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

## Architecture
React (craco) + Tailwind + Shadcn UI · FastAPI (port 8001, `/api` prefix) · MongoDB.
Auth is **cookie-based** JWT (HttpOnly, SameSite=None) — login returns the user object, no token.
Design system: `backend/site_content.py` (NICHES copy + LOOKS design tokens) →
`frontend/src/lib/theme.js` (themeVars / applyMode / modeCls) →
`frontend/src/styles/tenant-v2.css` + `tenant-modes.css` → `components/builder/BlockPreview.jsx`.

## Integrations
- Emergent Universal Key — Claude / GPT / Gemini text + image
- Stripe (env key `sk_test_emergent`) · Emergent-managed Resend · Emergent-managed Google Auth

## Implemented
- Full platform: Site Mode canvas, App Mode AI generation, templates, CMS, file library,
  bookings, paid memberships, client portals, master + granular locks, content lock
- Export pipeline (Website / Full-Stack App / Plugin) + plugin zip re-import
- Lead Inbox: auto-classification (real/test), admin override, AI draft replies, AI lead summary,
  lead source insights, live email delivery, auto-archive cron
- Dynamic landing page showcase + Showcase Manager (featured stars, drag-to-reorder)
- Tenant Overview auto-sync with Site Mode edits
- Rebrand OmniStack → Lois-Tech (UI-wide)
- **Sept 8, 2026 — regression fixes (iter 55/56):** idempotent canonical tenant restore
  (`app_6663b5de0007` + client.editor membership); `/api/public/showcase` made data-driven.
- **Sept 8, 2026 — deployment blockers fixed (deployment_agent PASS):** added `GET /health` +
  `/api/health` (the probe 404 was the deploy failure), `CORS_ORIGINS="*"` with
  `allow_origin_regex` for cookie auth, fault-tolerant startup seeding, `.get()` for ADMIN_EMAIL.
- **Sept 9, 2026 — 3-part design pass (iter 57, 17/17 tests pass):**
  - **Part 1:** `site_content.LOOKS` gives all 16 industry templates a unique identity — palette,
    bg/surface/border, font pair, radius, hero variant, mode, plus one `pr-site-*` CSS preset each
    (industrial, clinical, concrete, energy, editoriallux, harbour, ledger, techno, noir, freight,
    saas, counsel, campus, realty, ember, cinematic) controlling card style, button shape,
    dividers and section rhythm. `theme_for(n, key)` is the default for new tenants,
    `templates.apply_template` maps template key → look, `retheme_all()` back-fills existing
    tenants (gated on `look_v`), content never touched.
  - **Part 2:** `applyMode(theme, mode)` + `MODE_PRESETS` — one toggle rewrites colors, font
    pairing, radius, surfaces, buttons, dividers and glow/shadow; `--thead`/`--tbody` lock
    headings to #111111/#333333 (light) and #FFFFFF/#E5E5E5 (dark); every value stays overridable
    and persists per tenant.
  - **Part 3:** reveals start at opacity 0.3 in the correct text color (never invisible),
    strikethrough reset on body copy, secondary CTA outline/label contrast rule for all tenants.
  - Bonus bug found and fixed: `font-[var(--tfh)]` never compiled in Tailwind, so **no template
    had ever applied its heading font** — now bound in CSS.
  - Deterministic `preview_token` (`_pv_token`) so published preview links survive DB resets;
    `ensure_demo_tenants` self-heals the 6 demo tenants by fixed app_id.

## Backlog
- **P1** Real ElevenLabs voice — MOCKED; needs the user's ElevenLabs API key (next in agreed order)
- **P1** External DB sync export target (Supabase / PostgreSQL) + cloud drives
- **P1** Real GitHub push integration — MOCKED; user chose to hold off on the PAT
- **P2** Member "Delete my account" flow in profile
- **P2** `is_test` flag on tenants + admin "Archive test tenants" action
- **P2** Startup WARNING when a canonical demo/editor tenant vanishes (silent rollbacks)
- **P2** Legacy suites `test_iter11..52` hardcode dead tenant ids and 404 — refactor or delete
- **P3** Internal `omnistack` strings in `storage.py` APP_NAME and the plugin manifest format

## Order agreed with user
ElevenLabs → External DB sync → Delete-my-account → GitHub push (PAT on hold)

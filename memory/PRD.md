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
- **Tenants are NEVER created automatically.** Only three explicit admin actions can insert a
  tenant: `POST /api/apps` (New project), plugin-ZIP import, and website/ZIP import from the New
  project dialog. Template redesigns, theme changes, defaults and migrations may only modify
  template definitions and platform defaults — never create tenant records.
- Removing a tenant means **archive** (`archived: true`): hidden from the workspace, site offline,
  but pages, leads, bookings, members and files are retained and restorable.
- **Every lead from every tenant lands in the admin global inbox** (`GET /api/inbox`), including
  archived tenants and tenants that no longer exist ("Removed tenant").

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

## Current data state (Sept 9, 2026)
0 active tenants · 7 archived and recoverable (Maison Verde, Northwind Roofing, Orbit Customer
Success, Northline Freight Systems, Forge Athletic Club, Meridian Wealth Partners, Nocturne
Studios) · 5 leads retained, all visible in the admin inbox.

## Backlog
- **P1** Real ElevenLabs voice — MOCKED; needs the user's ElevenLabs API key (next in agreed order)
- **P1** External DB sync export target (Supabase / PostgreSQL) + cloud drives
- **P1** Real GitHub push integration — MOCKED; user chose to hold off on the PAT
- **P2** Member "Delete my account" flow in profile
- **P2** Template gallery: preview all 16 template designs before creating a tenant
- **P2** Legacy suites `test_iter11..52` hardcode dead tenant ids and 404 — refactor or delete
- **P3** Internal `omnistack` strings in `storage.py` APP_NAME and the plugin manifest format

## Order agreed with user
ElevenLabs → External DB sync → Delete-my-account → GitHub push (PAT on hold)

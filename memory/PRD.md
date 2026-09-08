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

## Backlog
- **P1** Real GitHub push (currently MOCKED — needs a user PAT)
- **P1** Live ElevenLabs / Resend keys (MOCKED / graceful fallback)
- **P1** Real sync/export to client Supabase / Postgres / Google Drive / Dropbox (credential UI built, transport pending)
- **P2** Retrofit existing tenants to `design_v2` on demand (one-click "Upgrade design" per tenant)
- **P2** Per-section design presets (editorial / bold / minimal) on top of design_v2
- **P2** Lock audit trail view (who locked what, when) in the Activity tab

## Testing
- Reports: `/app/test_reports/iteration_27.json … iteration_36.json` (33–36 this session, all passing)
- Backend suites: `/app/backend/tests/test_iter33_*.py`, `test_iter34_master_and_granular_locks.py`, iter35/36 design suites
- Credentials: `/app/memory/test_credentials.md`

## Guardrails learned
- Never regenerate/overwrite tenant pages without the content lock check (`assert_unlocked`)
- Declare all React state before any effect that references it (Builder.jsx crash cause)
- A `transform` on an ancestor kills `position: sticky` — keep navbars outside motion wrappers
- `_clean_theme` only strips Roboto/Arial/Times now; Inter is a first-class default

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

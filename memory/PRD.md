# PRD — Agency Showcase & Multi-Tenant App Platform

## Problem
Build a production-ready dashboard for an agency to host, manage, showcase and hand off multiple distinct client web/mobile apps from a single workspace.

## Personas
- Agency owner (Jay @ Lucio Digital) — creates, manages, and hands off apps.
- Client — invited as viewer/editor/admin to their own app tenant only.

## Core Requirements
1. Master agency dashboard — 5+ client app cards, status pills, metrics, industry filter, search.
2. Frame.ai-style block builder — hero, features, pricing, contact, chart blocks with AI prompt editor.
3. Client Handoff & Export tab — .zip source bundle (real) + iOS/Android build panel (MOCKED) + Client Transfer Mode toggle.
4. Multi-tenant RBAC — owner/admin/editor/viewer roles per app, activity log, notifications.
5. Dual auth — JWT email/password + Emergent Google OAuth.

## Implemented (Feb 2026)
- Backend: FastAPI + Mongo, dual auth, apps CRUD, pages/blocks CRUD, memberships/RBAC, activity logs, notifications, .zip export, MOCKED mobile export, Claude Sonnet 5 AI block editor.
- Frontend: Landing page with video hero, Login/Register (JWT) + Google OAuth button, AuthCallback, Dashboard grid with filters, App detail with 5 tabs (Overview, Builder, Handoff, Activity, Members), block builder with drag-to-reorder and AI prompt panel.
- Seed: 6 demo apps for admin `jaybernabe@luciodigital.com`.

## Backlog (P1/P2)
- Real drag-and-drop reorder via `@dnd-kit` (currently up/down buttons)
- Custom domains per tenant + DNS panel
- Real CI/CD for mobile builds (currently mocked)
- Stripe billing for tiered agency plans
- Team-level audit log CSV export
- Password reset email flow (Resend)

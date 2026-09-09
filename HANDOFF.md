# Lois-Tech — Client Handoff Guide

Everything a new owner needs to run this platform on their own infrastructure. No Emergent account is required.

## 1. What the stack is

| Layer | Tech | Notes |
|---|---|---|
| Frontend | React 19 + **Vite 6** + TypeScript-ready + Tailwind + shadcn/ui | `yarn build` → static `build/`, any CDN or nginx |
| Backend | FastAPI (Python 3.11) | Single ASGI app, all routes under `/api` |
| Database | MongoDB 7 | One database, `DB_NAME` |
| Files | Object storage OR MongoDB GridFS | `STORAGE_DRIVER` |
| AI | Emergent Universal Key **or** your own OpenAI / Anthropic / Gemini key | `backend/llm_provider.py` |

## 2. Configuration

Copy the examples and fill them in — nothing else in the code reads secrets:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Required: `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `FRONTEND_URL`, `ADMIN_EMAIL`, and `REACT_APP_BACKEND_URL` on the frontend.

## 3. Bring your own AI keys (no platform lock-in)

All model calls go through one module: `backend/llm_provider.py`.

- **Emergent mode** — `EMERGENT_LLM_KEY` set: text, images, TTS and video route through the Emergent proxy.
- **BYO mode** — no Emergent key, but any of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` set: text runs on litellm straight against that provider; `OPENAI_API_KEY` also powers image generation and text-to-speech.
  - The in-app model catalogue (`backend/ai_models.py`) lists Emergent's model ids. If your provider account doesn't expose them, set `LLM_MODEL_OVERRIDE=gpt-4o-mini` (or any model id you do have) and every text call uses it.
  - Video generation needs `FAL_KEY` (Fal.ai) outside Emergent mode; otherwise the Media Studio hides the video action.
- **No key at all** — the app runs fine; AI endpoints return a clear "no LLM key configured" error and everything else (sites, CMS, leads, exports, billing) keeps working.

## 4. File storage

- `STORAGE_DRIVER=proxy` (default) uses Emergent object storage and needs `EMERGENT_LLM_KEY`.
- `STORAGE_DRIVER=gridfs` stores every upload inside MongoDB (GridFS, `assets.*` collections) — nothing else to provision, and `mongodump` backs up your files along with your data. Serving and downloads work identically; only the driver changes.

## 5. Authentication

Two independent paths:

- **Email + password (JWT)** — fully self-contained. Works anywhere, no third party. This is the recommended handoff default.
- **Google sign-in** — currently uses Emergent's managed OAuth broker. If you leave Emergent, hide the "Continue with Google" button (`frontend/src/pages/Login.jsx`, `Register.jsx`) or swap in your own Google OAuth client; nothing else depends on it.

Admin rights are granted to the address in `ADMIN_EMAIL`.

## 6. Optional integrations

| Feature | Key | Behaviour without it |
|---|---|---|
| Payments | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Billing/checkout unavailable, rest of app unaffected |
| Voiceovers | `ELEVENLABS_API_KEY` (or in-app setting) | Falls back to OpenAI TTS, else hidden |
| Custom tenant domains | `DNS_CNAME_TARGET` | ⚠️ **Must be overridden** when self-hosting — it defaults to a Lois-Tech hostname, so the DNS instructions shown to your tenants would otherwise point at the original agency's infrastructure. Set it to your own ingress hostname. |

## 7. Data ownership

- **Client Handoff Bundle** (Handoff & Export tab → *Build Handoff Bundle*) → one zip with the static
  site, the full-stack app code, all records as JSON, every uploaded file, a ready Supabase
  `migration.sql`, `.env.example` and a written self-host guide.
- **Supabase export** (same tab) → push a tenant straight into the client's own Supabase Postgres
  (tables + rows + RLS), or download the `.sql` migration and run it themselves.
- Every tenant also has **Data export** → ZIP with all JSON records plus original files
  (`/api/apps/{id}/data-export`).
- Site/app exports produce plain HTML/CSS/JS and full-stack starter packages — no runtime dependency
  on this platform.

See `DEPLOYMENT.md` for the step-by-step self-host run.

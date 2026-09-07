# Auth Testing Playbook — Agency Multi-Tenant Platform

## Dual Auth Support
Both flows coexist:
1. **JWT email/password** — cookies `access_token` + `refresh_token`
2. **Emergent Google OAuth** — cookie `session_token`, exchanged from `#session_id=` URL fragment

## Seeded Admin
- Email: `jaybernabe@luciodigital.com`
- Password: `Lucio2026!`

## JWT Endpoints
- `POST /api/auth/register` — body `{email,password,name}`
- `POST /api/auth/login` — body `{email,password}` → sets cookies + returns user
- `GET /api/auth/me` — reads cookie or Bearer token, returns user
- `POST /api/auth/logout`

## Emergent Google Flow
1. Frontend Login button → `https://auth.emergentagent.com/?redirect=${origin}/dashboard`
2. Google returns to `/dashboard#session_id=xxx`
3. Frontend AuthCallback detects `session_id` from `useLocation().hash` (NOT `window.location.hash`)
4. AuthCallback POSTs `session_id` to `/api/auth/session` (backend)
5. Backend calls `https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data` with `X-Session-ID`
6. Backend upserts user, stores session row, sets `session_token` httpOnly cookie
7. Frontend redirects to `/dashboard`

## Curl smoke test
```bash
API=https://app-showcase-pro-4.preview.emergentagent.com
curl -c c.txt -X POST $API/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"jaybernabe@luciodigital.com","password":"Lucio2026!"}'
curl -b c.txt $API/api/auth/me
curl -b c.txt $API/api/apps
```

## Failure Indicators
- `/api/auth/me` returns 401 after login → cookie samesite/secure misconfig
- `/api/apps` returns empty on fresh install → seed did not run
- Callback stuck on `/dashboard#session_id=...` → frontend reads `window.location.hash` instead of `useLocation().hash`

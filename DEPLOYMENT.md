# Self-hosting Lois-Tech

## Option A — Docker Compose (fastest)

```bash
cp backend/.env.example backend/.env      # fill in JWT_SECRET, ADMIN_EMAIL, AI keys
cp frontend/.env.example frontend/.env
PUBLIC_URL=http://localhost:8080 docker compose up -d --build
```

- App: http://localhost:8080 (nginx serves the build and proxies `/api` to the backend)
- API health: http://localhost:8080/health
- Mongo persists in the `mongo_data` volume; with `STORAGE_DRIVER=gridfs` your uploads live there too.

For a real domain: put your reverse proxy / TLS in front of port 8080 and rebuild the frontend with
`PUBLIC_URL=https://app.yourdomain.com docker compose up -d --build` (the frontend bakes
`REACT_APP_BACKEND_URL` at build time), and set `FRONTEND_URL` to the same value in `backend/.env`.

Recommended for a self-hosted install: `STORAGE_DRIVER=gridfs` (uploads stored in your own MongoDB).

## Option B — Manual (no Docker)

Prerequisites: Python 3.11, Node 20, Yarn, MongoDB 7.

```bash
# backend
cd backend
pip install --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001

# frontend (new shell)
cd frontend
yarn install
yarn build          # static output in frontend/build — serve with nginx/Caddy/S3+CDN
# or: yarn start    # dev server on :3000
```

`emergentintegrations` is only needed in Emergent mode. In BYO mode you can drop that line from
`requirements.txt` and install the rest from PyPI as normal.

## Health checks & monitoring

- `GET /health` → `{"status":"ok"}` (also `GET /api/health`) — use it for liveness/readiness probes.
- Backend logs to stdout; with compose use `docker compose logs -f backend`.

## First run

1. Open the app and register with the address you put in `ADMIN_EMAIL` — that account gets platform admin rights.
2. Create your first tenant, or apply one of the 32 templates from the Template Gallery.
3. No demo/seed tenants are created automatically.

## Backups

```bash
docker compose exec -T mongo mongodump --archive --db "$DB_NAME" > backup-$(date +%F).archive
```

That single archive contains records **and** uploaded files when `STORAGE_DRIVER=gridfs`. Restore with `mongorestore --archive`.

# Deployment

Target: **Vercel** (frontend) + **Render** (API) + **Neon** (Postgres). Free tiers sleep, cap hours and can change — do not treat them as always-on or permanently free.

The app also runs entirely locally via Docker Compose.

## Local

1. Copy `.env.example` to `.env`.
2. `docker compose up --build`  
   or: Postgres on `DATABASE_URL`, `backend` venv + `python manage.py migrate && python manage.py createcachetable && python manage.py runserver`, `frontend` `npm run dev`.
3. Frontend proxies `/api` to the backend (`VITE_API_PROXY_TARGET`).

## Neon

Create a database. Use a connection string with `sslmode=require` as `DATABASE_URL`.

## Render

Blueprint: `infrastructure/render.yaml`. Root directory `backend`, Docker runtime.

Required env:

- `DJANGO_SETTINGS_MODULE=config.settings.prod`
- `DJANGO_SECRET_KEY` (50+ random chars)
- `DJANGO_ALLOWED_HOSTS` (your Render host)
- `DATABASE_URL`
- `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` (https:// your Vercel host)
- PayPal and LLM keys as needed
- SMTP vars if you want real email; otherwise delivery mode is `disabled` and the UI says so

Health: `GET /api/health/ready/`.

The Vercel `/api` rewrite keeps cookies first-party (`SameSite=Lax`). Only set `SESSION_COOKIE_SAMESITE=None` if the browser calls Render directly.

## Vercel

- Root: `frontend`
- Build: `npm run build`
- Copy `infrastructure/vercel.json` to `frontend/vercel.json` and replace the Render host in the `/api` rewrite.
- Leave `VITE_API_BASE_URL` empty so the SPA uses same-origin `/api`.

## First admin

```
python manage.py createsuperuser
```

That account is `super_admin` and can toggle seller second-factor on `/app/admin`.

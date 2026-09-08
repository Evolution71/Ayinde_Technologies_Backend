# Ayinde Technologies — Backend

FastAPI backend with a real database, user accounts, and login-gated
content — nothing about the site's data is hardcoded into route handlers
anymore.

## Structure

```
backend/
├── main.py           <- app setup: middleware, routers, startup seeding
├── database.py        <- SQLAlchemy engine/session
├── models.py           <- User, Service, TeamMember, Project, Course, Enrollment, ContactMessage
├── schemas.py           <- Pydantic request/response shapes
├── auth.py               <- password hashing, JWT tokens, get_current_user
├── security.py             <- captcha, rate limiting, security headers
├── seed.py                  <- inserts starter rows into an empty database
└── routers/
    ├── auth.py       <- /api/auth/register, /login, /me
    ├── services.py    <- /api/services (public)
    ├── team.py         <- /api/team (public)
    ├── projects.py      <- /api/projects (login required)
    ├── courses.py        <- /api/courses (login required) + enroll
    ├── contact.py         <- /api/contact (captcha required)
    └── captcha.py          <- /api/captcha
```

## Run locally

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and set a real `SECRET_KEY` — generate one with:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Then start it:
```bash
uvicorn main:app --reload --port 8000
```

A local `ayinde.db` (SQLite) is created automatically on first run, with
starter services/team/projects/courses seeded in. Check
`http://localhost:8000/health`.

## What's actually in the database now

Nothing is hardcoded into the API responses anymore — `seed.py` inserts
starter rows once, and every request after that is a real query against
the database. Add, edit, or remove rows directly in the database (or build
an admin endpoint later) and the API reflects it immediately.

## Authentication

- `POST /api/auth/register` — name, email, password (min 8 characters,
  needs a letter and a number), plus captcha_token/captcha_answer. Returns a JWT.
- `POST /api/auth/login` — email + password, plus captcha_token/captcha_answer
  (a captcha is now required on both sign-up and sign-in). Returns a JWT.
- `GET /api/auth/me` — current user, given a valid token.
- `GET /api/projects` and `GET /api/courses` both require a valid token
  (`Authorization: Bearer <token>`) — logged-out requests get a 401.
- `POST /api/courses/{id}/enroll` — starts a 30-day free trial for the
  current user on that course.

Tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60, set in
`.env`). There's no refresh-token flow yet — once a token expires, the user
logs in again.

## Payments (Flutterwave) — free trial, then pay to continue

Every course enrollment starts with a 30-day free trial
(`Enrollment.trial_ends_at`). `GET /api/courses` reports each course's
`access_status` as one of: `not_enrolled`, `trial`, `active` (paid), or
`expired`. Once `expired`, the frontend shows a "pay to continue" button.

- `POST /api/payments/initiate` — creates a Flutterwave Standard checkout
  link for a course.
- `POST /api/payments/verify` — confirms a transaction directly with
  Flutterwave (never trust the browser redirect's query params alone).
- `POST /api/payments/webhook` — Flutterwave calls this on payment events.
  Verified via the `verif-hash` header against `FLUTTERWAVE_SECRET_HASH`.

**This is built to work with zero payment configuration.** If
`FLUTTERWAVE_SECRET_KEY` isn't set in `.env`, `/api/payments/initiate`
returns a normal 200 response with `status: "unavailable"` and a friendly
message — not an error. Courses, trials, enrollment, login, everything
else on the site is completely unaffected either way, since this module is
additive and nothing else depends on it. Add your real Flutterwave keys to
`.env` whenever your merchant account is ready — no code changes needed,
just restart the server.

To go from "unavailable" to live payments:
1. Create a Flutterwave account at dashboard.flutterwave.com
2. Get your secret key from API settings, set `FLUTTERWAVE_SECRET_KEY`
3. Set up a webhook (Settings → Webhooks) pointing at
   `https://your-backend-url/api/payments/webhook`, with a secret hash you
   choose — set that same value as `FLUTTERWAVE_SECRET_HASH`
4. Adjust course prices directly in the database (`Course.price`,
   `Course.currency`) — the seeded prices are placeholders

## Security — what's actually implemented, and what isn't

Implemented, and tested:
- Passwords hashed with bcrypt (never stored in plain text)
- JWT-based login sessions, signed with `SECRET_KEY`
- **Captcha required on both sign-up and sign-in**, not just the contact form
- Rate limiting on login (10/min), register (5/min), and contact (5/min) —
  slows down brute-force and spam
- A self-hosted image CAPTCHA (no external API key needed)
- Security response headers (X-Frame-Options, HSTS, nosniff, Referrer-Policy)
- CORS locked to specific origins via `ALLOWED_ORIGINS`, not `*`
- Flutterwave webhook signature verification (rejects any request without
  the correct `verif-hash`, and rejects everything if no hash is configured)

**Not implemented, because it isn't something application code can
provide:** a real firewall or Web Application Firewall (WAF) — blocking
malicious traffic before it reaches this code, DDoS mitigation, IP
reputation blocking. That's infrastructure, sitting in front of the app,
not in it. When you deploy, turn on your host's or CDN's protection —
Cloudflare's free tier includes a basic WAF and DDoS protection, and
Railway/Render have their own baseline protections. If you want, I can
help you configure Cloudflare in front of the deployed site once it's live.

## Run with Docker

```bash
docker build -t ayinde-backend .
docker run -p 8000:8000 --env-file .env ayinde-backend
```

## Deploying

Any host that runs a Python web service works (Railway, Render, Fly.io).
Add a Postgres plugin and set `DATABASE_URL` to its connection string if
you want persistence beyond a single SQLite file. Set the start command to:
```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Pushing this as its own repo

```bash
cd backend
git init
git add .
git commit -m "Initial commit — Ayinde Technologies backend"
git remote add origin <your-backend-repo-url>
git push -u origin main
```

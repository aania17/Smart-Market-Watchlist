# Smart Market Watchlist

Smart Market Watchlist is an attention-first market monitoring application
built for the "Code by Groww" hackathon. It answers a focused question:

> **What deserves my attention since I last chose to check?**

Instead of treating a watchlist as a live ticker, the application compares
current prices with a durable per-watchlist baseline, highlights meaningful
changes, and explains the result in plain language. It supports stocks and
crypto, authenticated users, configurable sensitivity, optional position
sizes, and a shared market-data cache.

> **Reviewer setup:** See [setup.md](setup.md) for step-by-step installation,
> Supabase configuration, run commands, and the recommended product test flow.

> **Vercel deployment:** Deploy `frontend/` as the Vercel project root. The
> FastAPI backend must run separately on a persistent service such as Render,
> Railway, Fly.io, or a VM. See [setup.md](setup.md#81-vercel-deployment).

## What This Project Does

Most market watchlists show a stream of prices and percentage changes. They
answer **what the market is doing right now**, but they do not answer the more
useful personal question: **what changed since I last checked, and what should
I look at first?**

Smart Market Watchlist is designed around that second question. It creates a
personal, server-side checkpoint for each watchlist and compares new market
quotes against that checkpoint. The application then ranks meaningful moves,
compares stocks with a market index, and produces a short explanation instead
of asking the user to interpret a grid of numbers alone.

The project is intentionally focused on attention management rather than
trying to become a complete trading terminal. It does not place trades, make
investment recommendations, or claim to explain the news behind a price move.

## Typical User Journey

1. **Create an account** and sign in through the protected dashboard.
2. **Create or select a watchlist** for the instruments the user follows.
3. **Add stocks or crypto pairs**, such as `AAPL`, `MSFT`, or `BTC/USD`.
4. **Establish a baseline** by using the explicit “Mark as read & update”
   action. The current prices become the reference point for future changes.
5. **Return later** to see what moved since that acknowledgement. Reloading the
   page or switching tabs does not erase the changes.
6. **Scan the briefing first**, then inspect highlighted cards, relative moves,
   optional position impact, and the hourly graph for more detail.
7. **Tune sensitivity** when the default meaningful-move threshold is too high
   or too low for the watchlist.

## Main Capabilities

- **Personalized change detection**: compares quotes with the user's last
  acknowledged watchlist state rather than market open.
- **Attention-ranked dashboard**: meaningful changes appear first and receive a
  clear “Worth a look” treatment.
- **Market-relative context**: stock moves can be compared with `SPY` to help
  distinguish broad market movement from individual outperformance.
- **Plain-language briefing**: deterministic server-side text summarizes the
  most important current changes without requiring an LLM or news provider.
- **Explicit acknowledgement**: passive reads preserve alerts; only the user
  action that marks changes as read advances the baseline.
- **Position context**: optional unit counts turn percentage changes into an
  estimated native-currency price impact.
- **Stale-data transparency**: cached last-known-good quotes are labeled rather
  than presented as live data.
- **Hourly inspection**: an instrument-level graph shows the current day's
  available hourly price movement in UTC.
- **Shared upstream work**: the background poller refreshes the deduplicated
  union of watched symbols so repeated user views do not multiply provider
  requests.

## Technology Stack

| Layer | Technology | Role |
| --- | --- | --- |
| Frontend | React, Vite, Tailwind CSS | Dashboard, authentication screens, cards, and charts |
| API | FastAPI | Authentication, watchlist routes, and market-view responses |
| Persistence | SQLAlchemy + Supabase Postgres | Users, watchlists, items, and acknowledgement snapshots |
| Local fallback | SQLite | Optional local development database |
| Market data | Alpaca Market Data API | Stock and crypto quotes and hourly bars |
| Authentication | bcrypt + JWT | Password hashing and authenticated API access |

## Product Behavior

### Meaningful changes

Each available instrument receives two signals:

- **Change since last acknowledged visit**: the percentage difference between
  the current quote and the server-side snapshot saved for the watchlist.
  This is not calculated from market open, browser state, or local storage.
- **Relative move versus the index**: for stocks, the instrument's move since
  the previous close minus the configured index baseline's move. The default
  index is `SPY`. Crypto deliberately has no equivalent signal because there
  is no clean, consistent market baseline in this product's data model.

A signal is meaningful when either absolute value reaches the watchlist's
configured threshold. The default threshold is `2.0%`, and users can tune it
between `0.1%` and `20.0%`.

### Explicit acknowledgement

Reading data and acknowledging data are separate actions:

1. Page loads, reloads, and watchlist switches call `/view` without changing
   the baseline. A user can refresh repeatedly without losing an alert.
2. The **Mark as read & update** action calls `/view?update_baseline=true`.
   Only then are current prices and the acknowledgement timestamp saved as
   the next baseline.

This preserves the difference between “I looked at the screen” and “I have
processed these changes.”

### Briefing and move groups

The `/view` response also includes a deterministic, server-generated briefing
such as:

> Since your last visit, 2 holdings have moved meaningfully. AAPL is 3.1% up.

Meaningful, non-stale instruments with similar direction and magnitude may be
shown as a current-view group. These groups are intentionally transparent
heuristics. They are not historical correlation, sector attribution, or news
analysis.

### Optional position context

Users may attach a positive unit count to an instrument. When both a unit count
and a previous snapshot exist, the API returns native quote-currency impact:

`quantity × (current price − previous snapshot price)`

The application does not convert this value to INR or another currency, and it
does not attempt to model cost basis, portfolio valuation, or realized profit.

## Architecture

```text
Frontend (React + Vite)
        |
        | JWT-authenticated REST requests
        v
Backend (FastAPI)
  |-- Auth and ownership checks
  |-- Watchlist and snapshot persistence (SQLAlchemy)
  |-- Change detection and briefing composition
  |-- Shared quote cache
  |-- Background quote poller
        |
        v
Alpaca Market Data API
```

### Backend modules

- `app/main.py`: FastAPI routes and the read/acknowledge view flow.
- `app/auth.py`: JWT authentication and password verification.
- `app/models.py`: users, watchlists, watchlist items, and price snapshots.
- `app/crud.py`: database operations and ownership-scoped mutations.
- `app/change_detection.py`: percentage changes, relative moves, and impact.
- `app/briefing.py`: template-based briefing text and heuristic move groups.
- `app/market_data.py`: Alpaca client and shared quote/bar interfaces.
- `app/market_data_cache.py`: in-process last-known-good quote cache.
- `app/poller.py`: periodic refresh of the deduplicated set of watched symbols.

The poller refreshes the union of symbols watched by all users. Therefore, ten
users watching the same symbol do not create ten independent upstream refresh
jobs in a single backend process.

## API Overview

All watchlist routes require a bearer token returned by `/auth/login`.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/auth/signup` | Create an account |
| `POST` | `/auth/login` | Return a JWT access token |
| `GET` | `/auth/me` | Return the authenticated user |
| `GET` | `/watchlists` | List the user's watchlists |
| `POST` | `/watchlists` | Create a watchlist |
| `DELETE` | `/watchlists/{id}` | Delete an owned watchlist |
| `GET` | `/watchlists/{id}/view` | Read current prices and signals without changing the baseline |
| `GET` | `/watchlists/{id}/view?update_baseline=true` | Read and acknowledge the current signals |
| `PATCH` | `/watchlists/{id}/sensitivity` | Update the meaningful-change threshold |
| `POST` | `/watchlists/{id}/items` | Add a stock or crypto symbol |
| `PATCH` | `/watchlists/{id}/items/quantity?symbol=AAPL` | Set or clear an item's unit count |
| `DELETE` | `/watchlists/{id}/items?symbol=AAPL` | Remove an item |
| `GET` | `/watchlists/{id}/hourly` | Load the current day's hourly chart data |
| `GET` | `/health` | Check backend availability |

The primary `/view` response contains the watchlist, items, signals, briefing,
and move groups. It computes the response from the old snapshot before any
optional acknowledgement writes the new snapshot.

## Local Development

### Prerequisites

- Python 3.10 or newer
- Node.js 18 or newer and npm
- Alpaca API credentials for live quotes
- A Supabase project with a Postgres database

### Backend setup

From the repository root:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and set:

```env
SECRET_KEY=replace-with-a-long-random-value
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
ALPACA_API_KEY=your-alpaca-key
ALPACA_SECRET_KEY=your-alpaca-secret
```

To get the database URL in Supabase, open **Project Settings → Database →
Connect**, choose the **Session pooler** connection string, and replace the
password placeholder. Keep the `?sslmode=require` query parameter. If the
database password contains characters such as `@`, `:`, `/`, or `#`, URL-encode
the password before inserting it into the connection string.

Start the API:

```powershell
uvicorn app.main:app --reload
```

The backend is available at `http://localhost:8000`.

- OpenAPI documentation: `http://localhost:8000/docs`
- ReDoc documentation: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

The background poller starts with the application. If Alpaca credentials are
missing or invalid, the application remains available but quote refreshes will
fail and the backend will log the failure.

### Frontend setup

In a second terminal:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

The frontend is available at `http://localhost:5173`. The default
`frontend/.env` value is:

```env
VITE_API_URL=http://localhost:8000
```

Useful frontend commands:

```powershell
npm run lint
npm run build
npm run preview
```

## Docker

The repository includes a backend Dockerfile and a development-oriented
`docker-compose.yml`:

```powershell
docker compose up --build
```

The API will be exposed on `http://localhost:8000`. For a deployed setup,
provide production values for `SECRET_KEY`, `DATABASE_URL`,
`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, and `CORS_ORIGINS` rather than relying
on development defaults. The current compose file is intentionally minimal
and starts the backend only; the Vite frontend is run separately during local
development. The compose file reads `backend/.env` and does not hardcode the
database credentials.

## Vercel Deployment

Vercel hosts the React/Vite frontend. It does not replace the backend: this
application's FastAPI service starts a background quote poller and uses a
process-local cache, so the API should run on a persistent backend service.

1. Deploy `backend/` to Render, Railway, Fly.io, or another service that can
  run `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
2. Set the backend's `SECRET_KEY`, `DATABASE_URL`, `ALPACA_API_KEY`,
  `ALPACA_SECRET_KEY`, and `CORS_ORIGINS` environment variables. Set
  `CORS_ORIGINS` to the final Vercel URL, for example
  `https://your-app.vercel.app`.
3. Create a Vercel project from this repository and set **Root Directory** to
  `frontend`.
4. Use the detected Vite framework and the default build command `npm run build`.
  The included `frontend/vercel.json` preserves React Router routes by
  rewriting browser paths to `index.html`.
5. Add the Vercel environment variable `VITE_API_URL` with the deployed
  backend URL, for example `https://your-api.example.com`.
6. Redeploy the frontend after setting `VITE_API_URL`, then verify `/health`,
  signup, login, and watchlist loading from the Vercel URL.

Do not add backend secrets to Vercel. `VITE_*` values are shipped to the
browser, so `VITE_API_URL` must contain only the public API URL.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `SECRET_KEY` | Development placeholder | JWT signing key; replace before deployment |
| `DATABASE_URL` | Supabase Postgres URL | SQLAlchemy database URL; SQLite remains available as a local fallback |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed frontend origins |
| `ALPACA_API_KEY` | Empty | Alpaca market-data credential |
| `ALPACA_SECRET_KEY` | Empty | Alpaca market-data credential |
| `ALPACA_DATA_BASE_URL` | Alpaca data URL | Market-data API base URL |
| `INDEX_BASELINE_SYMBOL` | `SPY` | Stock comparison baseline |
| `QUOTE_POLL_INTERVAL_SECONDS` | `45` | Background quote refresh interval |

On startup, the application creates the SQLAlchemy tables if they do not yet
exist. This is convenient for a fresh Supabase project. For production schema
changes, use a formal migration tool such as Alembic rather than relying on
`create_all()`.

### Moving existing SQLite data

Changing `DATABASE_URL` points the application at a new database; it does not
copy the existing `backend/app.db` data. For a fresh hackathon deployment,
starting the application against Supabase is enough and creates empty tables.
If the existing local users and watchlists must be preserved, export the
SQLite tables and import them into Supabase, or use a migration utility before
switching the deployed `DATABASE_URL`. Do not copy passwords or credentials
into a migration script.

## Data and Failure Handling

- Quotes are fetched through one provider and normalized into shared `Quote`
  and `Bar` structures.
- The cache can serve a last-known-good quote when a fresh quote is unavailable.
  Such signals are marked `is_stale` so the UI does not present them as live.
- Symbols with no available quote are omitted from the signal list rather than
  being assigned fabricated values.
- A first visit has no previous snapshot, so percentage change and impact are
  `null` until an acknowledgement baseline exists.
- Crypto receives absolute move signals but no index-relative signal.

## Deliberate Scope Boundaries

The following choices are intentional:

- Briefings are deterministic templates, not LLM output.
- News and headline correlation are excluded to avoid a second unreliable live
  dependency during a demo.
- Move groups are current-view heuristics, not statistical correlation or
  sector classification.
- Native quote-currency impact is informational; FX, cost basis, and complete
  portfolio accounting are outside the product scope.
- The quote cache is an in-process dictionary. For a multi-process deployment,
  its internals should move to a shared store such as Redis while preserving
  the existing caller interface.

## Security and Deployment Notes

- Passwords are hashed with Passlib and bcrypt; `bcrypt==4.0.1` is pinned for
  compatibility with the current Passlib version.
- JWTs scope watchlist access to the authenticated user.
- The current hackathon frontend stores the short-lived JWT in browser
  `localStorage` for persistence across reloads. For production, replace this
  with an `HttpOnly`, `Secure`, `SameSite` cookie plus CSRF protection so an
  XSS bug cannot directly read the bearer token.
- Do not commit `.env` files or production credentials.
- Replace the development `SECRET_KEY` and configure a persistent production
  database before deployment.
- Configure the deployed frontend origin in `CORS_ORIGINS`.

## Supported Symbol Formats

- Stocks: plain tickers such as `AAPL`, `MSFT`, or `BRK-B`.
- Crypto: Alpaca pair format such as `BTC/USD` or `ETH/USD`.

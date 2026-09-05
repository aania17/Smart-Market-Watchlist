# Smart Market Watchlist: Implementation Reference

This document describes the application as implemented in the repository. It is intended to be the detailed technical and product reference for the current hackathon build.

## 1. Product Overview

Smart Market Watchlist is an authenticated market-monitoring application for stocks and crypto pairs. Its core question is:

> What deserves my attention since I last chose to check?

The application is intentionally an attention-management tool rather than a trading terminal. It compares current market quotes with a durable, per-watchlist acknowledgement baseline, identifies meaningful movement, ranks the most important instruments first, and explains the result with deterministic text.

### Included capabilities

- User signup and login.
- JWT-protected API access.
- Multiple personal watchlists.
- Stock and crypto instruments in the same application.
- Current quote display through Alpaca Market Data API.
- Per-watchlist, server-side acknowledgement snapshots.
- Meaningful-move detection using configurable sensitivity.
- Stock-relative performance versus a configurable index, defaulting to `SPY`.
- Deterministic plain-language briefings.
- Heuristic groups for instruments moving in a similar direction and magnitude.
- Optional unit quantities and estimated native-currency impact.
- Stale-data indicators when cached quotes cannot be refreshed.
- Current-day UTC hourly price graphs.
- A shared in-process quote cache and background polling loop.
- SQLite fallback for local development and PostgreSQL/Supabase support.
- Docker support for the backend.

### Explicitly excluded capabilities

- Trade placement, order management, or brokerage integration.
- Investment advice or recommendations.
- News, headline, or event correlation.
- LLM-generated explanations.
- Statistical correlation or sector classification.
- Portfolio accounting, cost basis, realized profit, or loss calculations.
- Foreign-exchange conversion of position impact.
- Persistent storage of live quotes in the database.
- Multi-process or multi-instance shared caching.

## 2. Repository Layout

```text
.
|-- README.md                         Product overview and architecture
|-- setup.md                          Setup, reviewer flow, troubleshooting
|-- implementation.md                 This implementation reference
|-- docker-compose.yml                Backend-only Docker Compose service
|-- backend/
|   |-- Dockerfile                    Python container image
|   |-- requirements.txt              Pinned Python dependencies
|   `-- app/
|       |-- __init__.py
|       |-- auth.py                   Password hashing and JWT authentication
|       |-- briefing.py               Briefing and move-group heuristics
|       |-- change_detection.py       Signal and impact calculations
|       |-- config.py                 Environment-backed settings
|       |-- crud.py                   Database operations
|       |-- database.py               SQLAlchemy engine and session setup
|       |-- main.py                   FastAPI app and all routes
|       |-- market_data.py             Alpaca API client and normalized data types
|       |-- market_data_cache.py       Process-local quote cache
|       |-- models.py                 SQLAlchemy database models
|       |-- poller.py                 Background quote refresh loop
|       |-- quotes_service.py          Cache-first quote lookup
|       `-- schemas.py                Pydantic request and response models
`-- frontend/
    |-- index.html                    Vite HTML entry point
    |-- package.json                  NPM scripts and dependencies
    |-- vite.config.js                Vite React plugin configuration
    |-- tailwind.config.js            Tailwind theme and colors
    |-- postcss.config.js             Tailwind/PostCSS configuration
    |-- README.md                     Vite template notes
    |-- public/
    |   |-- favicon.svg
    |   `-- icons.svg
    `-- src/
        |-- App.jsx                   Browser routes and providers
        |-- index.css                 Tailwind imports and theme overrides
        |-- main.jsx                  React root mounting
        |-- api/
        |   |-- client.js              Axios client and JWT interceptors
        |   `-- watchlists.js          Watchlist API functions
        |-- components/
        |   |-- AddSymbolForm.jsx      Instrument entry form
        |   |-- HourlyDashboard.jsx    Hourly chart modal
        |   |-- ProtectedRoute.jsx     Authenticated-route guard
        |   `-- SignalCard.jsx          Instrument signal card
        |-- context/
        |   `-- AuthContext.jsx        Login state and token lifecycle
        `-- pages/
            |-- Dashboard.jsx          Main watchlist experience
            |-- Login.jsx              Login screen
            `-- Signup.jsx             Account creation screen
```

## 3. System Architecture

```text
React + Vite frontend
        |
        | Axios REST requests with JWT bearer token
        v
FastAPI backend
  |-- Authentication and ownership checks
  |-- Watchlist CRUD
  |-- Baseline snapshot persistence
  |-- Change detection and briefing generation
  |-- Cache-first quote access
  |-- Current-day hourly bars
  `-- Background poller
        |
        v
Alpaca Market Data API

SQLAlchemy
  |-- SQLite for local fallback
  `-- PostgreSQL/Supabase for recommended deployment
```

The browser never receives Alpaca credentials. The backend is the only component that calls Alpaca. The frontend communicates with the backend using `VITE_API_URL`, defaulting to `http://localhost:8000`.

## 4. Runtime Configuration

Settings are defined in `backend/app/config.py` using `pydantic-settings`. A `.env` file is loaded from the backend process working directory. Unknown environment variables are ignored.

| Variable | Default | Purpose |
|---|---|---|
| `PROJECT_NAME` | `Hackathon Starter` | FastAPI application title |
| `SECRET_KEY` | `change-me-before-you-deploy` | JWT signing secret; replace before deployment |
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | JWT lifetime, 24 hours |
| `DATABASE_URL` | `sqlite:///./app.db` | SQLAlchemy database URL |
| `CORS_ORIGINS` | `[`"`http://localhost:5173`"`]` | Allowed browser origins |
| `ALPACA_API_KEY` | Empty | Alpaca API key |
| `ALPACA_SECRET_KEY` | Empty | Alpaca API secret |
| `ALPACA_DATA_BASE_URL` | `https://data.alpaca.markets` | Alpaca market-data base URL |
| `INDEX_BASELINE_SYMBOL` | `SPY` | Stock relative-performance baseline |
| `QUOTE_POLL_INTERVAL_SECONDS` | `45` | Background polling interval |

`backend/.env.example` is expected to contain the primary secret, database, and Alpaca settings. The frontend uses:

```env
VITE_API_URL=http://localhost:8000
```

### Database URL behavior

- `postgres://...` is normalized to `postgresql+psycopg://...`.
- `postgresql://...` is normalized to `postgresql+psycopg://...`.
- SQLite URLs are left unchanged and receive `check_same_thread=False`.
- SQLAlchemy uses `pool_pre_ping=True`.
- A database session is created per request and always closed by the `get_db` dependency.

### Startup schema behavior

`main.py` calls `Base.metadata.create_all(bind=engine)` at import time. For SQLite, `ensure_schema_compatibility()` also adds the `meaningful_threshold_pct` and `quantity` columns when upgrading an older local database. Production schema evolution should use a migration system such as Alembic rather than relying on `create_all()`.

## 5. Backend Dependencies

The backend pins the following packages in `backend/requirements.txt`:

- `fastapi==0.115.0`: HTTP API framework.
- `uvicorn[standard]==0.30.6`: ASGI server.
- `sqlalchemy==2.0.35`: ORM and database access.
- `python-jose[cryptography]==3.3.0`: JWT encoding and decoding.
- `passlib==1.7.4`: password hashing interface.
- `bcrypt==4.0.1`: pinned bcrypt implementation for Passlib compatibility.
- `python-multipart==0.0.9`: form parsing for OAuth2 login.
- `pydantic==2.9.2`: validation and serialization.
- `email-validator==2.2.0`: email validation.
- `httpx==0.27.2`: synchronous Alpaca HTTP requests.
- `pydantic-settings==2.5.2`: environment-backed configuration.
- `python-dotenv==1.0.1`: `.env` loading.
- `psycopg[binary]==3.2.3`: PostgreSQL driver.

## 6. Database Model

### `users`

Defined by `User` in `backend/app/models.py`.

| Column | Type | Behavior |
|---|---|---|
| `id` | Integer | Primary key and index |
| `email` | String | Required, unique, indexed |
| `hashed_password` | String | Required; stores bcrypt hash only |
| `full_name` | String | Nullable |
| `created_at` | DateTime | UTC default |

A user owns zero or more watchlists. Deleting a user cascades through the relationship in the ORM.

### `watchlists`

Defined by `Watchlist`.

| Column | Type | Behavior |
|---|---|---|
| `id` | Integer | Primary key and index |
| `owner_id` | Integer | Required foreign key to `users.id`, indexed |
| `name` | String | Required; default `My Watchlist` |
| `created_at` | DateTime | UTC default |
| `last_viewed_at` | DateTime | Nullable acknowledgement timestamp |
| `meaningful_threshold_pct` | Float | Required; default `2.0` |

A watchlist owns items and price snapshots. ORM relationships use delete-orphan cascading for both collections.

### `watchlist_items`

Defined by `WatchlistItem`.

| Column | Type | Behavior |
|---|---|---|
| `id` | Integer | Primary key and index |
| `watchlist_id` | Integer | Required foreign key, indexed |
| `symbol` | String | Required normalized instrument symbol |
| `asset_class` | String | `stock` or `crypto` |
| `quantity` | Float | Nullable positive unit count |
| `added_at` | DateTime | UTC default |

There is a unique constraint on `(watchlist_id, symbol)`. The same symbol can exist in different users' watchlists and in different asset classes only if the symbol strings are distinct.

### `price_snapshots`

Defined by `PriceSnapshot`.

| Column | Type | Behavior |
|---|---|---|
| `id` | Integer | Primary key and index |
| `watchlist_id` | Integer | Required foreign key, indexed |
| `symbol` | String | Snapshot instrument |
| `price` | Float | Required price at acknowledgement |
| `captured_at` | DateTime | Required timestamp |

There is a unique constraint on `(watchlist_id, symbol)`. A snapshot is the last explicitly acknowledged price, not a live quote. It is overwritten on acknowledgement.

Live quotes are never stored in these tables. They are held in the process-local quote cache.

## 7. Validation and Serialization

All request and response contracts are defined in `backend/app/schemas.py`.

### Authentication schemas

`UserCreate`:

- `email`: valid `EmailStr`.
- `password`: 6 to 72 characters.
- `full_name`: optional, maximum 100 characters.

`UserLogin` exists with email and 1-to-72-character password validation, but the current login route uses FastAPI's `OAuth2PasswordRequestForm` instead.

`UserOut` returns `id`, `email`, `full_name`, and `created_at`.

`Token` returns `access_token` and `token_type`, with `token_type` defaulting to `bearer`.

### Watchlist schemas

`WatchlistCreate`:

- Name defaults to `My Watchlist`.
- Name length is 1 to 100 characters.
- Whitespace is trimmed.
- A name that becomes blank after trimming is rejected.

`WatchlistOut` returns `id`, `name`, `created_at`, `last_viewed_at`, and `meaningful_threshold_pct`.

`SensitivityUpdate` accepts `meaningful_threshold_pct` from `0.1` through `20.0`, inclusive.

### Instrument schemas

`WatchlistItemCreate`:

- `symbol` length is 1 to 20 characters before normalization.
- `asset_class` must be exactly `stock` or `crypto`.
- `quantity` is optional and, when supplied, must be greater than zero.
- Stock symbols are trimmed and uppercased.
- Stock symbols may contain alphanumeric characters, periods, and hyphens.
- Stock symbols have an effective maximum length of 10 characters.
- Crypto symbols are trimmed and uppercased.
- Crypto symbols must be `BASE/QUOTE`, with both sides alphanumeric.

`QuantityUpdate` accepts a positive quantity or `null`. Sending `null` clears the stored quantity.

### Signal schemas

`ChangeSignalOut` contains:

- `symbol`
- `asset_class`
- `current_price`
- `as_of`
- `change_since_last_visit_pct`
- `last_visit_price`
- `last_visit_at`
- `relative_move_vs_index_pct`
- `quantity`
- `impact`
- `is_stale`
- `is_meaningful`

`MoveGroupOut` contains `direction`, `symbols`, and `average_move_pct`.

`WatchlistViewOut` contains `watchlist`, `items`, `signals`, `briefing`, and `move_groups`.

`HourlyPointOut` contains a timestamp and price. `HourlySeriesOut` contains `symbol`, `asset_class`, `points`, and optional `change_pct`.

## 8. Authentication and Authorization

### Signup

`POST /auth/signup` accepts JSON matching `UserCreate`. The email is checked for an existing exact match. Duplicate emails return HTTP 400 with `Email already registered`. New passwords are hashed with Passlib bcrypt before persistence. Successful creation returns HTTP 201 and `UserOut`.

### Login

`POST /auth/login` consumes URL-encoded OAuth2 form fields:

- `username`: treated as the user's email.
- `password`: plaintext password for verification.

Invalid email or password returns HTTP 401 with `Incorrect email or password`. Successful login returns a JWT with a string user ID in its `sub` claim and an expiration determined by `ACCESS_TOKEN_EXPIRE_MINUTES`.

### Current user

`GET /auth/me` returns the authenticated `UserOut` and requires a bearer token.

`get_current_user()` decodes the token using the configured secret and algorithm, requires a valid `sub`, converts it to an integer, and verifies that the user exists. Malformed, expired, invalid, or unknown-user tokens return HTTP 401 with a `WWW-Authenticate: Bearer` header.

### Ownership enforcement

All watchlist and item routes resolve the requested watchlist through both its ID and the authenticated user's ID. A watchlist owned by another user is indistinguishable from a missing watchlist and returns HTTP 404.

## 9. Market Data Integration

`backend/app/market_data.py` is the only module that talks directly to Alpaca.

### Normalized types

`AssetClass` has two values:

- `stock`
- `crypto`

`Quote` contains the symbol, asset class, current price, previous close, and provider timestamp. Its `change_pct_since_prev_close` property returns the rounded percentage from previous close, or `null` when previous close is absent or falsey.

`Bar` contains a symbol, close price, and timestamp.

### Alpaca endpoints

Stocks use:

- `GET /v2/stocks/snapshots`
- `GET /v2/stocks/bars`
- `feed=iex`

Crypto uses:

- `GET /v1beta3/crypto/us/snapshots`
- `GET /v1beta3/crypto/us/bars`

The client sends `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY` headers and uses a five-second HTTP timeout.

### Snapshot behavior

`get_snapshots()` batches symbols by asset class. Empty symbol lists immediately return an empty dictionary. Missing symbols in an otherwise successful response are omitted. Symbols without a latest trade price are also omitted; the application never invents a price.

Stock snapshots are read from the symbol-keyed response object. Crypto snapshots are read from the nested `snapshots` envelope. Alpaca timestamps are normalized from RFC-3339 strings by replacing `Z` with a UTC offset and truncating fractional seconds to Python's microsecond precision.

### Historical bars

`get_daily_bars()` requests one-day bars and returns normalized `Bar` objects. It is implemented but is not currently called by the application.

`get_hourly_bars()` requests one-hour bars, with `limit=24`, for the requested start and end timestamps. It is used by the hourly chart route for the current UTC day.

### Failure behavior

HTTP failures and timeout failures are converted to `MarketDataUnavailable`. A total provider failure does not crash a watchlist request. Callers either use cached values or omit symbols with no available data.

## 10. Quote Cache and Poller

### Process-local cache

`backend/app/market_data_cache.py` exposes a module-level `quote_cache` singleton. Entries are keyed by `(asset_class, symbol)` and contain:

- The normalized `Quote`.
- A local `fetched_at` timestamp.
- A `stale` flag.

`set()` stores fresh data and clears the stale flag. `mark_stale()` preserves an existing quote while marking it stale. `get_many()` returns only cached entries. The cache is not persisted and is not shared between processes.

### Cache-first quote service

`get_current_quotes()`:

1. Looks for each requested symbol in the cache.
2. Returns cached quotes immediately.
3. Synchronously fetches only cache misses.
4. Stores newly fetched quotes in the cache.
5. Silently omits symbols when the provider is unavailable.

`get_index_quote()` obtains the configured baseline symbol through the same service. `is_stale()` reads the cache flag for a symbol.

### Background polling

The FastAPI startup event launches `asyncio.create_task(run_poller(SessionLocal))`. The poller runs for the lifetime of the process.

Each cycle:

1. Queries all distinct symbols in all users' watchlist items.
2. Groups them by stock or crypto.
3. Fetches one batch per asset class.
4. Stores returned quotes as fresh cache entries.
5. Marks missing or failed symbols stale if a previous cached quote exists.
6. Sleeps for `QUOTE_POLL_INTERVAL_SECONDS`, defaulting to 45 seconds.

Blocking database and provider work runs in a worker thread using `asyncio.to_thread`. Unexpected cycle errors are logged and do not terminate the loop.

The deduplicated union means multiple users watching the same symbol share one upstream refresh in a single backend process. A multi-process deployment would need a shared cache such as Redis to preserve that property across workers.

## 11. Change Detection

`backend/app/change_detection.py` constructs `ChangeSignal` objects.

### Change since acknowledgement

For a current price $P$ and prior acknowledged price $P_0$:

$$
\text{change since last visit} = \frac{P - P_0}{P_0} \times 100
$$

The value is rounded to four decimal places. It is `null` when there is no previous snapshot or the previous price is zero.

This is intentionally not a market-open comparison, browser-state comparison, or local-storage comparison.

### Relative move versus the index

For stocks only:

$$
\text{relative move} = \text{stock change since previous close} - \text{index change since previous close}
$$

The default index is `SPY`. A positive result means the stock outperformed the index; a negative result means it underperformed. Crypto receives no relative-move signal.

The index comparison is unavailable when the index quote or either previous-close value is unavailable.

### Position impact

When both a quantity and a prior snapshot exist:

$$
\text{impact} = \text{quantity} \times (\text{current price} - \text{last visit price})
$$

The result is rounded to two decimals. It is expressed in the quote's native currency and is not an account balance, cost-basis calculation, realized P/L calculation, or FX-converted value.

### Meaningful threshold

A signal is meaningful when either the absolute acknowledgement change or the absolute relative move is greater than or equal to the watchlist threshold. The persisted default is `2.0%`.

The API accepts `0.1%` to `20.0%`. The current dashboard range input displays `0.5%` to `10%` in `0.5%` increments, so the UI currently exposes a narrower range than the API.

## 12. Briefings and Move Groups

`backend/app/briefing.py` uses deterministic templates.

### Briefing

When there are no meaningful signals, the response is:

```text
Nothing has moved enough to deserve your attention since your last visit.
```

When meaningful signals exist, the briefing identifies:

- Whether the comparison is against `your last visit` or a formatted UTC time.
- The number of meaningful holdings.
- The largest meaningful acknowledgement move, when available.
- The first meaningful stock that is outperforming the index by at least the threshold, when one exists.

The wording uses singular `holding has` for one result and plural `holdings have` otherwise.

### Move groups

Move groups use only meaningful, non-stale signals that have an acknowledgement change. Signals are split into `up` and `down` based on the sign of that change.

For each direction:

1. Signals are sorted by absolute movement.
2. Signals are bucketed when their absolute moves differ by no more than one percentage point from the first signal in a bucket.
3. Buckets with at least two instruments become groups.
4. The group average is the rounded average of the signed acknowledgement changes.

These are current-view heuristics. They are not historical correlation, sector analysis, or causal attribution.

## 13. REST API

All endpoints under watchlists and all user-specific endpoints require `Authorization: Bearer <token>` unless stated otherwise. FastAPI also exposes generated OpenAPI documentation at `/docs` and ReDoc at `/redoc`.

### `GET /health`

Unauthenticated health check.

Response:

```json
{"status": "ok"}
```

### `POST /auth/signup`

Creates an account.

Request:

```json
{
  "email": "person@example.com",
  "password": "at-least-six-characters",
  "full_name": "Optional Name"
}
```

Returns HTTP 201 and the public user fields. Duplicate email returns HTTP 400.

### `POST /auth/login`

Consumes `application/x-www-form-urlencoded` fields `username` and `password`. The username is the email address.

Response:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

### `GET /auth/me`

Returns the current user's ID, email, optional full name, and creation timestamp.

### `GET /watchlists`

Lists only the authenticated user's watchlists.

### `POST /watchlists`

Creates a watchlist. The request body is `{ "name": "..." }`. The name is trimmed and must be nonblank. Returns HTTP 201.

### `DELETE /watchlists/{watchlist_id}`

Deletes an owned watchlist. Related items and snapshots are configured for ORM cascading. Returns HTTP 204.

### `POST /watchlists/{watchlist_id}/items`

Adds a stock or crypto item.

Request examples:

```json
{"symbol": "AAPL", "asset_class": "stock"}
{"symbol": "BTC/USD", "asset_class": "crypto"}
```

The backend normalizes symbols to uppercase. Adding an existing `(watchlist, symbol)` is idempotent and returns the existing item without changing its existing asset class or quantity.

### `PATCH /watchlists/{watchlist_id}/sensitivity`

Request:

```json
{"meaningful_threshold_pct": 3.5}
```

Accepts `0.1` through `20.0` and returns the updated watchlist.

### `PATCH /watchlists/{watchlist_id}/items/quantity?symbol=AAPL`

Request:

```json
{"quantity": 12}
```

Use `null` to clear the quantity. The symbol is a query parameter because crypto symbols contain `/`.

### `DELETE /watchlists/{watchlist_id}/items?symbol=AAPL`

Removes an item. The symbol is a query parameter for the same crypto-pair routing reason. The operation returns HTTP 204 and does not report whether a row existed.

### `GET /watchlists/{watchlist_id}/view`

Returns the current watchlist view without changing the acknowledgement baseline.

The optional query parameter is:

```text
update_baseline=false
```

The response contains:

```json
{
  "watchlist": {},
  "items": [],
  "signals": [],
  "briefing": "",
  "move_groups": []
}
```

The route reads old snapshots and the old `last_viewed_at`, obtains current quotes, calculates signals, creates the briefing and move groups, and sorts meaningful signals first.

### `GET /watchlists/{watchlist_id}/view?update_baseline=true`

Performs the same response calculation, then writes current available prices to `price_snapshots` and updates `watchlist.last_viewed_at`. The diff is always calculated before the write, so the acknowledgement response still describes the changes that were just acknowledged.

Only symbols with available quotes are written to the snapshot map. Missing quotes are not fabricated.

### `GET /watchlists/{watchlist_id}/hourly`

Returns one series per item using Alpaca one-hour bars from the beginning of the current UTC day through the request time. It returns a series with an empty `points` list when no bars are available for a symbol. Provider failure results in empty bar maps rather than an API crash.

`change_pct` is calculated from the first available hourly close to the last available hourly close.

## 14. Core View Request Sequence

For `GET /watchlists/{id}/view`:

1. Resolve the watchlist and enforce ownership.
2. Load all watchlist items.
3. Load the old symbol-to-snapshot map.
4. Save the old `last_viewed_at`.
5. Group symbols by asset class.
6. Get current quotes through the cache-first quote service.
7. Get the index quote if the watchlist contains at least one stock.
8. Omit items with no available current quote.
9. Build each signal against the old snapshot.
10. Calculate the briefing and move groups.
11. If `update_baseline=true`, upsert available prices and update the acknowledgement timestamp.
12. Sort signals so meaningful items appear first, then by absolute acknowledgement move.
13. Serialize the watchlist, all items, available signals, briefing, and move groups.

The important invariant is that passive reads do not update `price_snapshots` or `last_viewed_at`. Reloading, changing tabs, and switching watchlists therefore do not erase an alert.

## 15. Frontend Architecture

The frontend is a React 19 application bundled with Vite.

### Dependencies and scripts

Runtime dependencies:

- `react`
- `react-dom`
- `react-router-dom`
- `axios`

Development dependencies:

- `@vitejs/plugin-react`
- `vite`
- `tailwindcss`
- `postcss`
- `autoprefixer`
- `oxlint`
- React type packages

Scripts:

- `npm run dev`: starts Vite development server.
- `npm run build`: creates a production build.
- `npm run lint`: runs `oxlint src`.
- `npm run preview`: serves the production build locally.

React Compiler is not enabled in the current Vite template.

### Browser routes

`App.jsx` defines:

- `/login`: public login page.
- `/signup`: public signup page.
- `/`: protected dashboard.

`AuthProvider` wraps all routes. `ProtectedRoute` displays a loading state while authentication is restored, redirects unauthenticated users to `/login`, and renders the dashboard for authenticated users.

### Axios client

`src/api/client.js` creates an Axios client with `VITE_API_URL` or `http://localhost:8000`.

A request interceptor reads `localStorage.token` and adds `Authorization: Bearer <token>` to every request when present.

A response interceptor removes the token and redirects to `/login` for HTTP 401 responses, except for `/auth/*` requests so login and signup can display their own errors.

### Authentication context

`AuthContext.jsx` stores:

- `user`
- `loading`
- `login(email, password)`
- `signup(email, password, fullName)`
- `logout()`

On mount, an existing local-storage token is validated using `GET /auth/me`. An invalid token is removed. Login sends URL-encoded OAuth2 fields, saves the returned JWT, then loads the current user. Signup creates the account and immediately logs in. Logout removes the token and clears the user.

The current frontend stores the JWT in browser `localStorage`. For a production security posture, an `HttpOnly`, `Secure`, `SameSite` cookie with CSRF protection would avoid exposing the bearer token directly to JavaScript.

## 16. Dashboard Behavior

`Dashboard.jsx` is the main application surface.

### Bootstrap

On first mount, the dashboard:

1. Lists the user's watchlists.
2. Creates `My Watchlist` automatically when none exist.
3. Selects the first watchlist.
4. Loads its passive view.

A ref prevents duplicate bootstrap work.

### Watchlist management

The dashboard supports:

- Switching between watchlists.
- Creating a named watchlist.
- Deleting a watchlist.
- Preventing deletion when it is the only remaining watchlist.
- Displaying the signed-in email.
- Logging out.

A locally maintained `Map` caches the latest view per watchlist for fast display while fresh data loads. A request ID ref prevents an older response from replacing a newer active-watchlist response.

### Sensitivity

The dashboard shows an attention-sensitivity range input and updates the threshold on every change. The current range is `0.5` to `10` in `0.5` increments, despite the backend accepting `0.1` to `20.0`.

After a successful update, the dashboard recalculates each visible signal's `is_meaningful` value locally and updates the cached view.

### Summary area

The dashboard displays:

- Instrument count.
- Stock count.
- Crypto count.
- Count of signals marked `Worth a look`.
- Last acknowledgement age in UTC.
- The server-generated briefing.
- Move-group text such as instruments moving together up or down.
- The explicit `Mark as read & update` action.

The button calls `/view?update_baseline=true`. Ordinary dashboard loads call `/view?update_baseline=false`.

### Instrument entry

`AddSymbolForm.jsx` provides:

- Free-text symbol input.
- Stock/Crypto selector.
- Client-side stock validation using an alphanumeric ticker with optional periods or hyphens.
- Client-side crypto validation using `BASE/QUOTE`.
- Busy state and API error display.
- Placeholder examples `AAPL` and `BTC/USD`.

After adding, the dashboard reloads the passive view. Backend validation remains authoritative.

### Instrument cards

`SignalCard.jsx` displays:

- Symbol and asset class.
- Current price with two decimal places.
- Provider timestamp in UTC.
- Stale-data badge when applicable.
- `Worth a look` badge for meaningful signals.
- Percentage since last visit.
- Stock-only relative movement versus `SPY`.
- First-view baseline message when no snapshot exists.
- Optional quantity editor.
- Estimated dollar-style impact since the last visit.
- Remove button.
- View graph button.

Cards are ordered with meaningful signals first and then by the largest available movement signal. Symbols with no current quote are rendered separately with a clearly labeled unavailable-data state and a graph option.

### Quantity editor

A card allows a user to add or edit a positive unit count. An empty value sends `null` and clears the quantity. The server persists the quantity. The dashboard updates the visible impact locally without requiring a full reload.

### Hourly graph

Clicking `View graph` opens `HourlyDashboard.jsx` as a modal. The dashboard requests all watchlist hourly series once per active watchlist and reuses the result for other cards. A request ref prevents duplicate concurrent requests for the same watchlist.

The modal includes:

- Instrument symbol.
- Current-day hourly movement percentage.
- SVG line chart.
- Up/down chart color.
- Grid lines and price labels.
- Three time labels in UTC.
- Data-point count.
- `Current day, UTC` label.
- Loading state.
- No-data state when fewer than two points are available.
- Close button and backdrop-click close behavior.

The chart uses a fixed internal view box of 920 by 380, calculates padded min/max bounds, and plots every returned point.

## 17. Styling and Visual System

Tailwind CSS is configured in `tailwind.config.js` with these custom colors:

- `background`: `#f8fafc`
- `surface`: `#ffffff`
- `primary`: `#0f172a`
- `muted`: `#64748b`
- `market-up`: `#00D09C`
- `market-down`: `#EB5B3C`
- `borders`: `#e2e8f0`

`index.css` imports Tailwind layers and provides:

- Global font and text rendering settings.
- Light radial background atmosphere.
- A dashboard grid pattern.
- Dark dashboard theme overrides through `data-theme="dark"`.
- Dark input, border, surface, and muted-text overrides.
- Standard inherited button, input, and select typography.

The dashboard uses a dark market-grid shell with light data surfaces, blue action accents, green positive movement, red negative movement, and amber attention badges. Login and signup use light centered forms.

`index.html` currently uses the document title `frontend` and references `/favicon.svg`.

## 18. Deployment and Local Development

### Prerequisites

- Python 3.10 or newer.
- Node.js 18 or newer with npm.
- Git.
- Alpaca Market Data credentials for live quotes.
- Supabase PostgreSQL is recommended for a shared deployment; SQLite is available for local fallback.

### Backend setup

From the repository root:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

The backend defaults to `http://localhost:8000`.

Useful endpoints:

- `http://localhost:8000/health`
- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

### Frontend setup

In another terminal:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

The Vite server normally uses `http://localhost:5173`.

### Docker

From the repository root:

```powershell
docker compose up --build
```

The compose file builds only the backend, maps host port 8000 to container port 8000, loads `backend/.env`, and mounts `./backend` at `/app`. The frontend still runs separately with Vite.

The backend Dockerfile uses `python:3.12-slim`, installs the pinned requirements, copies the backend source, and runs Uvicorn on `0.0.0.0:8000`.

### Validation commands

Backend compilation:

```powershell
cd backend
.\venv\Scripts\python.exe -m compileall app
```

Frontend lint and production build:

```powershell
cd frontend
npm run lint
npm run build
```

Database connectivity check:

```powershell
cd backend
.\venv\Scripts\python.exe -c "from sqlalchemy import text; from app.database import engine; print(engine.connect().execute(text('select 1')).scalar())"
```

## 19. Recommended Manual Acceptance Flow

1. Open the frontend.
2. Create an account through `Sign up`.
3. Confirm the dashboard auto-creates a default watchlist.
4. Add `AAPL` as a stock.
5. Optionally add `BTC/USD` as crypto when crypto data is available.
6. Confirm current prices or a clear unavailable-data state.
7. Use `Mark as read & update` to create the first baseline.
8. Reload without acknowledging and confirm the baseline remains unchanged.
9. Change the sensitivity slider and confirm meaningful badges update.
10. Add a quantity to an instrument and confirm impact appears when a baseline exists.
11. Open `View graph` and inspect the current-day hourly data.
12. Use `Mark as read & update` again and confirm the acknowledgement timestamp and baseline advance.
13. Create a second watchlist and switch between lists.
14. Remove an instrument and verify it no longer appears.
15. Delete a watchlist and verify the final remaining list cannot be deleted.
16. Log out and confirm the protected dashboard redirects to login.

## 20. Failure and Edge-Case Behavior

- Invalid or expired JWT: HTTP 401; frontend clears the token and redirects to login for non-auth requests.
- Duplicate signup email: HTTP 400.
- Invalid credentials: HTTP 401.
- Unknown or unauthorized watchlist: HTTP 404.
- Invalid stock or crypto format: Pydantic validation error.
- Duplicate instrument add: idempotent existing-item response.
- Missing Alpaca credentials or provider outage: backend remains available; missing symbols are omitted, and existing cached quotes can be labeled stale.
- Cached provider quote after refresh failure: shown with `is_stale=true` and a visible `Stale data` badge.
- No quote and no cached value: item remains in the item list but is omitted from `signals`; the dashboard shows registered/unavailable state.
- New instrument with no acknowledgement snapshot: change percentage and impact are `null`; the card explains that the first view is building a baseline.
- No previous close: relative move versus index is `null`.
- Crypto instrument: no relative index signal.
- No hourly bars or fewer than two points: chart displays no hourly data available.
- Passive view: does not alter the acknowledgement baseline.
- Acknowledgement view: writes only prices currently available in that response.
- Old concurrent dashboard response: ignored using request IDs when it is no longer current.
- Last watchlist deletion: blocked in the frontend with `Keep at least one watchlist.`

## 21. Security and Operations Notes

- Never commit `backend/.env` or `frontend/.env`.
- Never expose Alpaca credentials through frontend environment variables.
- Replace the default JWT secret before deployment.
- Use fresh demo credentials and rotate any credential exposed in a public issue, commit, screenshot, or chat.
- Use a persistent production database.
- Configure the deployed frontend origin in `CORS_ORIGINS`.
- The current local-storage JWT approach is acceptable for the hackathon flow but should be replaced with secure cookies and CSRF protection for production.
- The current poller is a fire-and-forget task and assumes a single backend process.
- The in-process cache is lost on restart and is not shared across workers.
- Formal migrations should replace startup-only table creation for production schema management.

## 22. Known Implementation Notes

- `get_daily_bars()` exists in the provider client but is currently unused.
- `UserLogin` exists as a Pydantic schema but login currently uses `OAuth2PasswordRequestForm`.
- The default FastAPI project title remains `Hackathon Starter` unless `PROJECT_NAME` is overridden.
- The HTML document title remains `frontend` in the current `index.html`.
- The API threshold limits and dashboard slider limits are different, as described above.
- The frontend formats both stock and crypto prices with a dollar sign; the backend impact is described as native quote currency.
- The quote cache stores a local fetch timestamp, but the current UI surfaces the provider quote timestamp and stale status rather than the local fetch age.
- No automated test files are present in the repository. Current verification relies on compilation, lint/build commands, health checks, connectivity checks, and the documented manual flow.

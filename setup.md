# Setup and Run Instructions

This guide helps reviewers run Smart Market Watchlist locally and verify the main workflow.

## 1. Prerequisites

Install the following before starting:

- Python 3.10 or newer
- Node.js 18 or newer with npm
- Git
- A Supabase project with a Postgres database
- Alpaca Market Data API credentials for live stock and crypto quotes

The application can use SQLite for local fallback development, but the recommended setup uses Supabase Postgres.

## 2. Get the Project

```powershell
git clone https://github.com/aania17/Smart-Market-Watchlist.git
cd Smart-Market-Watchlist
```

If the repository is already open locally, start from the project root:

```text
C:\Users\<your-user>\Downloads\hackathon-starter
```

## 3. Configure the Backend

Create and activate a Python virtual environment:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `backend/.env` and fill in the values below:

```env
SECRET_KEY=replace-with-a-long-random-value
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
ALPACA_API_KEY=your-alpaca-api-key
ALPACA_SECRET_KEY=your-alpaca-secret-key
```

### Supabase database URL

In Supabase, open:

`Project Settings -> Database -> Connect -> Session pooler -> URI`

Copy the Postgres URI into `DATABASE_URL`. Keep `sslmode=require` at the end.

If the database password contains reserved URL characters, encode them before placing the password in the URL:

| Character | Encoded value |
| --- | --- |
| `@` | `%40` |
| `:` | `%3A` |
| `/` | `%2F` |
| `#` | `%23` |
| `[` | `%5B` |
| `]` | `%5D` |
| `%` | `%25` |

Do not include placeholder brackets around the password. For example, use:

```env
DATABASE_URL=postgresql://postgres.project-ref:myPassword@aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require
```

The backend creates the required tables automatically when the application starts against a fresh Supabase database.

## 4. Start the Backend

Keep the backend terminal open and run:

```powershell
uvicorn app.main:app --reload
```

The backend should be available at:

- API: http://localhost:8000
- Swagger documentation: http://localhost:8000/docs
- ReDoc documentation: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

Test the health endpoint in a browser or PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Expected response:

```text
status
------
ok
```

## 5. Configure and Start the Frontend

Open a second terminal. From the project root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
```

Confirm `frontend/.env` contains:

```env
VITE_API_URL=http://localhost:8000
```

Start the Vite development server:

```powershell
npm run dev
```

Open the URL shown by Vite, normally:

http://localhost:5173

## 6. Reviewer Test Flow

Use this sequence to verify the core product behavior:

1. Open the frontend URL.
2. Select **Sign up** and create a test account.
3. Log in with the new account.
4. Add a stock such as `AAPL`.
5. Add an optional crypto pair such as `BTC/USD` if crypto credentials/data are available.
6. Confirm the dashboard displays current prices or a clearly labeled unavailable-data state.
7. Use **Mark as read & update** to establish the first acknowledgement baseline.
8. Reload the page. The baseline should remain unchanged because passive reads do not acknowledge changes.
9. Adjust the attention sensitivity slider and confirm the meaningful-change labels update.
10. Optionally add a unit count to a symbol to view estimated native-currency impact.
11. Open **View graph** to inspect hourly movement.
12. Use **Mark as read & update** again to acknowledge the current changes and establish a new baseline.

## 7. Useful Validation Commands

Backend compilation:

```powershell
cd backend
.\venv\Scripts\python.exe -m compileall app
```

Frontend linting and production build:

```powershell
cd frontend
npm run lint
npm run build
```

Read-only Supabase connectivity test:

```powershell
cd backend
.\venv\Scripts\python.exe -c "from sqlalchemy import text; from app.database import engine; print(engine.connect().execute(text('select 1')).scalar())"
```

Expected result:

```text
1
```

## 8. Docker Option

The repository includes a backend Docker setup. Ensure `backend/.env` contains valid credentials, then run from the project root:

```powershell
docker compose up --build
```

The backend will be available at http://localhost:8000. Run the frontend separately with `npm run dev` from `frontend`.

## 8.1 Vercel Deployment

Vercel should host the React frontend from the `frontend/` directory. The
FastAPI backend should remain on a persistent service such as Render, Railway,
Fly.io, or a VM because it runs a background quote poller and maintains an
in-process quote cache. Vercel's request-driven functions are not a suitable
replacement for that long-running process.

### Deploy the backend

Deploy the `backend/` directory to your chosen persistent host with this
start command:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Configure these backend environment variables:

```env
SECRET_KEY=replace-with-a-long-random-value
DATABASE_URL=your-supabase-postgres-url
ALPACA_API_KEY=your-alpaca-api-key
ALPACA_SECRET_KEY=your-alpaca-secret-key
CORS_ORIGINS=https://your-app.vercel.app
```

Copy the resulting public API URL and confirm `https://your-api.example.com/health`
returns `{"status":"ok"}`.

### Deploy the frontend to Vercel

1. Import the GitHub repository into Vercel.
2. Set **Root Directory** to `frontend`.
3. Keep the Vite framework preset and `npm run build` build command.
4. Add this Vercel environment variable:

	```env
	VITE_API_URL=https://your-api.example.com
	```

5. Deploy or redeploy the project.

The included `frontend/vercel.json` rewrites all browser routes to
`index.html`, so `/login`, `/signup`, and `/` continue to work after a direct
refresh. Do not put `SECRET_KEY`, database credentials, or Alpaca credentials
in Vercel. Variables beginning with `VITE_` are exposed in the browser.

After deployment, test signup, login, `/health`, adding an instrument, and the
`Mark as read & update` flow. If the browser reports a CORS error, update the
backend `CORS_ORIGINS` value to the exact Vercel origin and restart the backend.

## 9. Troubleshooting

### `password authentication failed for user`

Reset the Supabase database password, copy the new Session pooler URI, and URL-encode reserved characters in the password.

### `could not translate host name` or connection timeout

Confirm the host and region were copied from Supabase exactly. Prefer the Session pooler URL on port `6543` when the direct database host on port `5432` is unreachable.

### The frontend cannot reach the backend

Confirm the backend is running on port `8000` and that `frontend/.env` contains:

```env
VITE_API_URL=http://localhost:8000
```

Restart the Vite server after changing `.env` values.

### No stock data appears

Confirm `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` are present in `backend/.env`. Check the backend terminal for provider errors. The application labels stale cached data and does not fabricate missing quotes.

### Login says credentials are invalid

The Supabase database starts empty unless data was migrated. Use **Sign up** to create the first account, then log in with that account.

### Port already in use

Stop the process using the port or start Vite on another port:

```powershell
npm run dev -- --port 5174
```

If the backend port must change, update `VITE_API_URL` to match it.

## 10. Security Notes

- Never commit `backend/.env` or `frontend/.env`.
- Never put Alpaca credentials in frontend environment variables.
- Use fresh credentials for reviewers or demos.
- Rotate credentials if they are ever pasted into a public issue, commit, screenshot, or chat.
- The `.env.example` files contain placeholders only.

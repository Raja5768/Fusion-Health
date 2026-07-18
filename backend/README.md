# Fusion Health Backend

This FastAPI service receives Apple Health activity from the iOS app. Automatic uploads keep one compact PostgreSQL row per calendar date containing only steps and active calories. Extended manual imports remain supported for compatibility but are not sent by the current app.

## Endpoints

- `GET /health` — deployment health check.
- `POST /api/v1/import/apple-health` — receive an iPhone HealthKit export.
- `GET /api/v1/export/latest` — retrieve the latest normalized export.
- `GET /api/v1/daily?limit=30` — retrieve stored daily steps and calories, newest first.
- `GET /api/v1/daily/{YYYY-MM-DD}` — retrieve steps and calories for one date.
- `GET /api/v1/summary/today` — retrieve a briefing-ready daily summary.
- `GET /docs` — interactive OpenAPI documentation.

Protected endpoints require `X-API-Key`. Configure the same secret as `FUSION_HEALTH_API_KEY` on the server and in the iOS app.

## Run locally

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export FUSION_HEALTH_API_KEY=fh_replace_with_a_long_random_secret
uvicorn app.main:app --reload
```

The local default uses SQLite. Set `DATABASE_URL` to a PostgreSQL connection string for hosted deployments.

## Deploy to Render

The repository-root `render.yaml` creates the API, a generated API key, and PostgreSQL automatically through a Render Blueprint.

1. Sign in to Render with GitHub.
2. Choose **New > Blueprint**.
3. Select the `Fusion-Health` repository and branch `agent/ios-app-redesign`.
4. Apply the Blueprint.
5. Open the web service's **Environment** page and securely copy `FUSION_HEALTH_API_KEY`.
6. In the iPhone app's **API** tab, enter the service URL and copied key.

Do not commit the generated API key. Free Render PostgreSQL databases currently expire after 30 days; upgrade or attach a permanent PostgreSQL provider before relying on it for long-term history.

Current hosted API: `https://fusion-health-api-qe6l.onrender.com`

## Automatic daily activity

The iOS app requests a background refresh shortly after local midnight. At the earliest time iOS permits, it uploads the completed previous calendar day's steps and active calories. It also retries whenever the app becomes active. Imports upsert `daily_activity` by date, so retries update the date instead of creating duplicate daily records. Today's live HealthKit data is display-only and is never uploaded.

Example:

```bash
curl -H "X-API-Key: $FUSION_HEALTH_API_KEY" \
  "https://fusion-health-api-qe6l.onrender.com/api/v1/daily?limit=7"
```

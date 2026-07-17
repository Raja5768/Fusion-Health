# Fusion Health

Fusion Health is a self-hosted wearable data MVP inspired by Open Wearables style architecture. It starts with WHOOP OAuth and sync, normalizes data into universal SQLite tables, exposes a single REST API, and generates a rules-first daily health decision summary.

## What works now

- FastAPI backend with SQLite.
- Local register/login and bearer token auth.
- Hashed API keys via `X-API-Key`.
- WHOOP OAuth connect flow and manual sync.
- Universal tables for users, providers, tokens, summaries, sleep, workouts, heart rate samples, recovery scores, API keys, and AI daily briefings.
- Apple Health import endpoint placeholder for a future iOS app.
- Rules-first daily decision engine with optional Ollama polishing.
- Basic local dashboard at `/`.
- Docker Compose local deployment.

## WHOOP setup

Create an app in the WHOOP Developer Dashboard and set the redirect URI to:

```text
http://localhost:8000/api/v1/auth/whoop/callback
```

WHOOP OAuth uses:

- Authorization URL: `https://api.prod.whoop.com/oauth/oauth2/auth`
- Token URL: `https://api.prod.whoop.com/oauth/oauth2/token`
- Data API base: `https://api.prod.whoop.com/developer/v2`

Requested scopes are configured in `.env`:

```text
offline read:profile read:recovery read:cycles read:sleep read:workout
```

## Local setup

```bash
cp .env.example .env
# edit .env with SECRET_KEY, WHOOP_CLIENT_ID, and WHOOP_CLIENT_SECRET
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://localhost:8000`.

## Docker

```bash
cp .env.example .env
# edit .env
docker compose up --build
```

SQLite is stored in `./data/fusion_health.db` when using Docker Compose.

## API quickstart

Register:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"change-me-please"}'
```

Generate an API key:

```bash
curl -X POST http://localhost:8000/api/v1/api-keys/generate \
  -H "Authorization: Bearer YOUR_LOCAL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"local script"}'
```

Sync WHOOP after connecting OAuth:

```bash
curl -X POST "http://localhost:8000/api/v1/sync/whoop?days=14" \
  -H "Authorization: Bearer YOUR_LOCAL_TOKEN"
```

## Universal endpoints

- `GET /api/v1/summary/today`
- `GET /api/v1/summary/yesterday`
- `GET /api/v1/sleep`
- `GET /api/v1/recovery`
- `GET /api/v1/workouts`
- `GET /api/v1/heart-rate`
- `GET /api/v1/body-metrics`
- `GET /api/v1/decision/today`
- `POST /api/v1/sync/whoop`
- `POST /api/v1/api-keys/generate`
- `DELETE /api/v1/api-keys/{key_id}`
- `DELETE /api/v1/me/data`

## Apple Health plan

The backend should not pull Apple Health directly. This repo now includes a lightweight SwiftUI companion app in `ios/FusionHealth` that:

1. Request HealthKit permissions on-device.
2. Read steps, sleep, heart rate, workouts, calories, and body metrics locally.
3. Convert data into Fusion Health normalized JSON.
4. Upload it to:

```text
POST /api/v1/import/apple-health
```

Use an API key with the iOS app by setting the `X-API-Key` header. On iPhone, use your backend machine's LAN address such as `http://192.168.1.10:8000`, not `localhost`.

Example payload:

```json
{
  "steps": [{ "date": "2026-07-06", "count": 8400 }],
  "sleep": [{ "start": "2026-07-05T23:00:00Z", "end": "2026-07-06T06:30:00Z", "sleep_hours": 7.5 }],
  "heart_rate": [{ "sampled_at": "2026-07-06T12:00:00Z", "bpm": 62, "context": "resting" }],
  "workouts": [{ "activity_name": "Run", "start": "2026-07-06T15:00:00Z", "end": "2026-07-06T15:35:00Z", "calories": 360 }],
  "calories": [],
  "body_metrics": []
}
```

## Decision engine

The MVP uses deterministic rules first:

- Sleep under 6 hours and recovery under 60 means rest or light workout.
- Recovery over 75 and sleep over 7 means intense workout is reasonable.
- High strain yesterday and low recovery today means active recovery.
- Elevated resting heart rate or low HRV adds cautionary actions.

Enable Ollama only if you want a local model to polish the wording:

```text
ENABLE_OLLAMA=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
```

If Ollama is unavailable, Fusion Health returns the rules-based mock briefing.

## Privacy and security defaults

- All data stays local by default.
- Provider tokens are encrypted at rest using `FUSION_ENCRYPTION_KEY` or a key derived from `SECRET_KEY`.
- API keys are stored hashed.
- Provider tokens are never returned by the API.
- `DELETE /api/v1/me/data` deletes normalized health data and AI briefings for the authenticated user.

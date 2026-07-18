# Fusion Health API

Version: `v1`

Format: JSON over HTTPS
Default development URL: `http://localhost:8000`

Fusion Health accepts normalized health records from the iOS companion app and exposes daily summaries and briefing-ready decisions to trusted clients. Apple Health data is read locally on the iPhone; the backend never connects directly to HealthKit.

> The current repository branch contains the iOS client. This document is the API contract the Fusion Health backend must implement.

## Base URL

All endpoints use the `/api/v1` prefix:

```text
https://health.example.com/api/v1
```

Use HTTPS for hosted deployments. Plain HTTP should only be used on a trusted local network during development.

## Authentication

### API key

The iOS import client authenticates with an API key:

```http
X-API-Key: fh_your_key
```

API keys must be stored hashed by the backend. The complete key is returned only when it is created. The iOS app stores it in the device Keychain.

### Bearer token

Interactive clients and Daily Briefing services may authenticate with a bearer token:

```http
Authorization: Bearer your_access_token
```

Unless an endpoint explicitly says otherwise, it requires either a valid API key or bearer token associated with the requesting user.

## Common conventions

- Timestamps use ISO 8601 UTC, for example `2026-07-16T14:30:00Z`.
- Calendar dates use `YYYY-MM-DD`.
- Durations are decimal hours unless the field name specifies another unit.
- Heart rate is measured in beats per minute (`bpm`).
- Energy is measured in kilocalories (`kcal`).
- Body mass is measured in kilograms (`kg`).
- Oxygen saturation is represented as a fraction from `0` to `1`.
- Unknown optional values should be omitted or sent as `null`.

## Errors

Errors use the HTTP status code and a JSON `detail` field:

```json
{
  "detail": "The API key is invalid or has been revoked."
}
```

Common status codes:

- `400` — malformed or semantically invalid request
- `401` — missing or invalid credentials
- `403` — authenticated but not permitted
- `404` — requested record does not exist
- `409` — request conflicts with existing state
- `422` — payload validation failed
- `429` — rate limit exceeded
- `500` — unexpected server failure

## Apple Health import

### Import normalized HealthKit data

```http
POST /api/v1/import/apple-health
Content-Type: application/json
X-API-Key: fh_your_key
```

Request:

```json
{
  "steps": [
    {
      "date": "2026-07-16",
      "count": 8420
    }
  ],
  "sleep": [
    {
      "start": "2026-07-15T23:00:00Z",
      "end": "2026-07-16T06:30:00Z",
      "sleep_hours": 7.5,
      "sleep_score": null
    }
  ],
  "heart_rate": [
    {
      "sampled_at": "2026-07-16T07:00:00Z",
      "bpm": 61,
      "context": "apple_health"
    }
  ],
  "workouts": [
    {
      "activity_name": "Run",
      "start": "2026-07-16T15:00:00Z",
      "end": "2026-07-16T15:35:00Z",
      "calories": 360,
      "average_heart_rate": 148
    }
  ],
  "calories": [
    {
      "date": "2026-07-16",
      "calories": 530
    }
  ],
  "body_metrics": [
    {
      "sampled_at": "2026-07-16T06:45:00Z",
      "type": "body_mass",
      "value": 72.4,
      "unit": "kg"
    }
  ]
}
```

Successful response (`200 OK`):

```json
{
  "provider": "Apple Health",
  "imported": {
    "steps": 1,
    "sleep": 1,
    "heart_rate": 1,
    "workouts": 1,
    "calories": 1,
    "body_metrics": 1
  },
  "imported_at": "2026-07-16T18:20:00Z"
}
```

Imports should be idempotent. The backend should derive a stable identity from the user, provider, sample type, timestamps, and source identifier so repeated iPhone syncs update or ignore existing samples instead of duplicating them.

## Daily summaries

### Get stored daily steps and calories

The iPhone automatically uploads only the completed previous day's steps and active calories after midnight. Today's live data is displayed on-device and is never uploaded. iOS chooses the exact background execution time; if it delays the task, Fusion Health retries when the app next opens. Each date is upserted, so a retry replaces that day's values and PostgreSQL retains one compact row per date.

```http
GET /api/v1/daily?limit=7
X-API-Key: fh_your_key
```

Response:

```json
[
  {
    "date": "2026-07-16",
    "steps": 8420,
    "calories": 530.0,
    "provider": "Apple Health",
    "updated_at": "2026-07-17T05:05:00Z"
  }
]
```

`limit` accepts `1` through `365` and defaults to `30`.

### Get one calendar date

```http
GET /api/v1/daily/2026-07-16
X-API-Key: fh_your_key
```

This returns one object in the same format or `404` when that date has not been uploaded.

### Get today's summary

```http
GET /api/v1/summary/today
Authorization: Bearer your_access_token
```

### Get yesterday's summary

```http
GET /api/v1/summary/yesterday
Authorization: Bearer your_access_token
```

Response:

```json
{
  "summary_date": "2026-07-16",
  "sleep_hours": 7.4,
  "recovery_score": 78,
  "strain": 6.2,
  "resting_heart_rate": 58,
  "hrv_ms": 52,
  "steps": 8420,
  "calories": 530,
  "provider": "Apple Health"
}
```

`recovery_score` and `strain` are normalized Fusion Health values. When a provider does not supply them, the backend may calculate them from personal baselines and should preserve the underlying measurements used in the calculation.

## Daily briefing

### Get today's decision

```http
GET /api/v1/decision/today
Authorization: Bearer your_access_token
```

Response:

```json
{
  "readiness_score": 82,
  "decision": "You are ready for a moderate-to-hard training day.",
  "why": [
    "You slept 7.4 hours.",
    "HRV is above your 14-day baseline.",
    "Resting heart rate is within your normal range."
  ],
  "recommended_actions": [
    "Complete your planned workout.",
    "Aim for 9000 steps.",
    "Start winding down by 10:30 PM."
  ],
  "data_sources": [
    "Apple Health"
  ]
}
```

The briefing engine should use normalized daily features and personal baselines rather than sending raw high-frequency heart-rate samples to a language model. Deterministic health rules should run before optional AI wording.

## Health history

The following authenticated endpoints return the current user's normalized records, ordered newest first:

```http
GET /api/v1/sleep
GET /api/v1/recovery
GET /api/v1/workouts
GET /api/v1/heart-rate
GET /api/v1/body-metrics
```

Production implementations should support `start`, `end`, `limit`, and cursor-based pagination query parameters.

Example:

```http
GET /api/v1/workouts?start=2026-07-01&end=2026-07-16&limit=50
```

## Accounts and credentials

### Register

```http
POST /api/v1/auth/register
Content-Type: application/json
```

```json
{
  "email": "you@example.com",
  "password": "a-long-unique-password",
  "full_name": "Example User"
}
```

### Log in

```http
POST /api/v1/auth/login
Content-Type: application/json
```

```json
{
  "email": "you@example.com",
  "password": "a-long-unique-password"
}
```

Token response:

```json
{
  "access_token": "token_value",
  "token_type": "bearer"
}
```

### Create an API key

```http
POST /api/v1/api-keys/generate
Authorization: Bearer your_access_token
Content-Type: application/json
```

```json
{
  "name": "My iPhone"
}
```

### Revoke an API key

```http
DELETE /api/v1/api-keys/{key_id}
Authorization: Bearer your_access_token
```

## Data deletion

### Delete all user health data

```http
DELETE /api/v1/me/data
Authorization: Bearer your_access_token
```

Successful response:

```json
{
  "status": "deleted"
}
```

The backend should delete normalized health records, generated briefings, provider tokens, and derived summaries according to its published retention policy.

## Security requirements

- Require HTTPS outside local development.
- Never log API keys, bearer tokens, or complete health payloads.
- Hash API keys and encrypt provider refresh tokens at rest.
- Scope every query by authenticated user ID.
- Validate timestamp ranges, units, numeric bounds, and payload sizes.
- Rate-limit authentication and import endpoints.
- Provide key rotation and immediate revocation.
- Keep an auditable record of imports without storing credentials in logs.
- Return the minimum data required by each client.

## cURL example

```bash
curl -X POST "https://health.example.com/api/v1/import/apple-health" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: fh_your_key" \
  -d '{"steps":[{"date":"2026-07-16","count":8420}],"sleep":[],"heart_rate":[],"workouts":[],"calories":[],"body_metrics":[]}'
```

## Compatibility

Breaking request or response changes require a new path version such as `/api/v2`. Fields may be added to `v1` responses, so clients must ignore unknown JSON properties.

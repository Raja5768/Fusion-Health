# Fusion Health iOS

This is a lightweight SwiftUI companion app for iPhone. It reads Apple Health data locally with HealthKit, converts it to the Fusion Health normalized JSON shape, and uploads it to the backend endpoint:

```text
POST /api/v1/import/apple-health
X-API-Key: fh_...
```

## What It Syncs

- Steps by day.
- Sleep sessions.
- Heart rate samples.
- Workouts.
- Active calories by day.
- Body mass samples.

## Run On iPhone

1. Open `ios/FusionHealth/FusionHealth.xcodeproj` in Xcode on a Mac.
2. Select the `FusionHealth` target.
3. In **Signing & Capabilities**, choose your Apple developer team.
4. Make sure **HealthKit** is enabled.
5. Connect your iPhone.
6. Build and run.

## Backend URL

Do not use `localhost` from the iPhone. Use your Mac or server LAN address instead:

```text
http://192.168.1.10:8000
```

Your iPhone and backend machine must be on the same Wi-Fi network unless the backend is exposed through a tunnel or hosted server.

## API Key

Generate a Fusion Health API key from the dashboard or API:

```bash
curl -X POST http://localhost:8000/api/v1/api-keys/generate \
  -H "Authorization: Bearer YOUR_LOCAL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"iPhone"}'
```

Paste the returned `api_key` into the app. The backend stores only the hash.

## Privacy

HealthKit data is read on-device. The app uploads only to the backend URL you enter. Provider tokens are not used by the iOS app.

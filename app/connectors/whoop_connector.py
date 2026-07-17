from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Provider, ProviderToken
from app.normalization.normalize_recovery import normalize_whoop_recovery
from app.normalization.normalize_sleep import normalize_whoop_sleep
from app.normalization.normalize_workouts import normalize_whoop_cycle, normalize_whoop_workout
from app.security import decrypt_value, encrypt_value, token_expiry


class WhoopConnector:
    AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
    TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
    API_BASE = "https://api.prod.whoop.com/developer/v2"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def exchange_code(self, code: str) -> dict[str, Any]:
        return await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.settings.whoop_redirect_uri,
                "client_id": self.settings.whoop_client_id,
                "client_secret": self.settings.whoop_client_secret,
            }
        )

    async def sync_user(self, db: Session, user_id: int, days: int = 14) -> dict[str, int]:
        provider = db.scalar(select(Provider).where(Provider.name == "whoop"))
        token = db.scalar(select(ProviderToken).where(ProviderToken.user_id == user_id, ProviderToken.provider_id == provider.id))
        if not token:
            raise HTTPException(status_code=400, detail="WHOOP is not connected")

        access_token = await self._valid_access_token(db, token)
        start = (datetime.utcnow() - timedelta(days=days)).isoformat(timespec="seconds") + "Z"
        counts = {"cycles": 0, "sleep_sessions": 0, "recoveries": 0, "workouts": 0, "heart_rate_samples": 0}

        cycles = await self._get_collection(access_token, "/cycle", {"start": start, "limit": 25})
        for cycle in cycles:
            normalize_whoop_cycle(db, user_id, cycle)
        counts["cycles"] = len(cycles)

        sleeps = await self._get_collection(access_token, "/activity/sleep", {"start": start, "limit": 25})
        for sleep in sleeps:
            normalize_whoop_sleep(db, user_id, sleep)
        counts["sleep_sessions"] = len(sleeps)

        recoveries = await self._get_collection(access_token, "/recovery", {"start": start, "limit": 25})
        for recovery in recoveries:
            normalize_whoop_recovery(db, user_id, recovery)
        counts["recoveries"] = len(recoveries)

        workouts = await self._get_collection(access_token, "/activity/workout", {"start": start, "limit": 25})
        for workout in workouts:
            normalize_whoop_workout(db, user_id, workout)
        counts["workouts"] = len(workouts)

        db.commit()
        return counts

    async def _valid_access_token(self, db: Session, token: ProviderToken) -> str:
        if token.expires_at and token.expires_at <= datetime.utcnow() and token.refresh_token_encrypted:
            refreshed = await self._token_request(
                {
                    "grant_type": "refresh_token",
                    "refresh_token": decrypt_value(token.refresh_token_encrypted),
                    "client_id": self.settings.whoop_client_id,
                    "client_secret": self.settings.whoop_client_secret,
                    "scope": "offline",
                }
            )
            token.access_token_encrypted = encrypt_value(refreshed["access_token"]) or ""
            token.refresh_token_encrypted = encrypt_value(refreshed.get("refresh_token"))
            token.expires_at = token_expiry(refreshed.get("expires_in"))
            token.scope = refreshed.get("scope", token.scope)
            db.commit()
        access_token = decrypt_value(token.access_token_encrypted)
        if not access_token:
            raise HTTPException(status_code=400, detail="WHOOP access token is unavailable")
        return access_token

    async def _token_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.whoop_client_id or not self.settings.whoop_client_secret:
            raise HTTPException(status_code=400, detail="WHOOP OAuth credentials are not configured")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(self.TOKEN_URL, data=payload, headers={"Accept": "application/json"})
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()

    async def _get_collection(self, access_token: str, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        next_token: str | None = None
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                query = dict(params)
                if next_token:
                    query["nextToken"] = next_token
                response = await client.get(
                    f"{self.API_BASE}{path}",
                    params=query,
                    headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                )
                if response.status_code >= 400:
                    raise HTTPException(status_code=response.status_code, detail=response.text)
                payload = response.json()
                records.extend(payload.get("records", []))
                next_token = payload.get("next_token")
                if not next_token:
                    break
        return records

import json
from datetime import date, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AiDailyBriefing, DailySummary


async def build_or_get_daily_briefing(db: Session, user_id: int, day: date) -> dict[str, object]:
    existing = db.scalar(select(AiDailyBriefing).where(AiDailyBriefing.user_id == user_id, AiDailyBriefing.briefing_date == day))
    if existing:
        return _briefing_to_dict(existing)

    today = db.scalar(select(DailySummary).where(DailySummary.user_id == user_id, DailySummary.summary_date == day))
    yesterday = db.scalar(select(DailySummary).where(DailySummary.user_id == user_id, DailySummary.summary_date == day - timedelta(days=1)))
    briefing = _rules_briefing(today, yesterday)
    briefing = await _maybe_ollama_polish(briefing, today, yesterday)

    record = AiDailyBriefing(
        user_id=user_id,
        briefing_date=day,
        readiness_score=briefing["readiness_score"],
        decision=briefing["decision"],
        why_json=json.dumps(briefing["why"]),
        recommended_actions_json=json.dumps(briefing["recommended_actions"]),
        data_sources_json=json.dumps(briefing["data_sources"]),
    )
    db.add(record)
    db.commit()
    return briefing


def _rules_briefing(today: DailySummary | None, yesterday: DailySummary | None) -> dict[str, object]:
    if not today:
        return {
            "readiness_score": 50,
            "decision": "Collect more data",
            "why": ["No summary is available for today"],
            "recommended_actions": ["Sync WHOOP", "Keep training easy until data is available", "Prioritize sleep tonight"],
            "data_sources": [],
        }

    sleep = today.sleep_hours or 0
    recovery = today.recovery_score or 50
    strain_yesterday = yesterday.strain if yesterday else None
    readiness = int(max(1, min(100, recovery * 0.7 + min(sleep, 8) / 8 * 30)))
    why: list[str] = []
    actions: list[str] = ["Hydrate early", "Sleep before 11 PM"]

    if sleep < 6 and recovery < 60:
        decision = "Rest or light workout recommended"
        why += ["Sleep was below target", "Recovery is low"]
        actions += ["30-minute walk", "Avoid intense training today"]
    elif recovery > 75 and sleep > 7:
        decision = "Intense workout is reasonable"
        why += ["Recovery is high", "Sleep was above target"]
        actions += ["Schedule your hardest training block", "Warm up thoroughly"]
    elif strain_yesterday and strain_yesterday > 14 and recovery < 60:
        decision = "Active recovery recommended"
        why += ["Yesterday strain was high", "Recovery is low today"]
        actions += ["Zone 1 cardio or mobility", "Delay intervals or heavy lifting"]
    else:
        decision = "Light workout recommended"
        why += ["Recovery is moderate", "No major red flags found"]
        actions += ["Easy aerobic session", "Stop if fatigue rises"]

    if today.resting_heart_rate and today.resting_heart_rate > 70:
        why.append("Resting heart rate is elevated")
        actions.append("Watch for fatigue or stress")
    if today.hrv_ms and today.hrv_ms < 40:
        why.append("HRV is below baseline threshold")
        actions.append("Reduce training intensity")

    return {
        "readiness_score": readiness,
        "decision": decision,
        "why": why,
        "recommended_actions": list(dict.fromkeys(actions)),
        "data_sources": [today.provider] if today.provider else [],
    }


async def _maybe_ollama_polish(briefing: dict[str, object], today: DailySummary | None, yesterday: DailySummary | None) -> dict[str, object]:
    settings = get_settings()
    if not settings.enable_ollama:
        return briefing
    prompt = (
        "Return only JSON with the same keys. Keep the medical tone cautious and concise. "
        f"Rules briefing: {json.dumps(briefing)}. Today: {today.__dict__ if today else None}. Yesterday: {yesterday.__dict__ if yesterday else None}"
    )
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={"model": settings.ollama_model, "prompt": prompt, "stream": False, "format": "json"},
            )
        response.raise_for_status()
        candidate = json.loads(response.json().get("response", "{}"))
        if set(briefing).issubset(candidate):
            return candidate
    except Exception:
        return briefing
    return briefing


def _briefing_to_dict(record: AiDailyBriefing) -> dict[str, object]:
    return {
        "readiness_score": record.readiness_score,
        "decision": record.decision,
        "why": json.loads(record.why_json),
        "recommended_actions": json.loads(record.recommended_actions_json),
        "data_sources": json.loads(record.data_sources_json),
    }

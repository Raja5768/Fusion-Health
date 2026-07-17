from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SleepSession
from app.normalization.utils import dump_raw, parse_dt


def normalize_whoop_sleep(db: Session, user_id: int, payload: dict) -> SleepSession:
    score = payload.get("score") or {}
    stage = score.get("stage_summary") or {}
    sleep_id = str(payload.get("id"))
    sleep = db.scalar(select(SleepSession).where(SleepSession.user_id == user_id, SleepSession.provider_sleep_id == sleep_id))
    if not sleep:
        sleep = SleepSession(user_id=user_id, provider="WHOOP", provider_sleep_id=sleep_id)
    sleep.start_time = parse_dt(payload.get("start"))
    sleep.end_time = parse_dt(payload.get("end"))
    sleep.sleep_hours = _millis_to_hours(stage.get("total_in_bed_time_milli") or stage.get("total_sleep_time_milli"))
    sleep.sleep_score = score.get("sleep_performance_percentage")
    sleep.raw_json = dump_raw(payload)
    db.add(sleep)
    return sleep


def _millis_to_hours(value: int | float | None) -> float | None:
    return round(float(value) / 1000 / 60 / 60, 2) if value is not None else None

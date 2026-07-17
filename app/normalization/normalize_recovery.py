from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailySummary, RecoveryScore
from app.normalization.utils import dump_raw, parse_day


def normalize_whoop_recovery(db: Session, user_id: int, payload: dict) -> RecoveryScore:
    score = payload.get("score") or {}
    day = parse_day(payload.get("created_at") or payload.get("updated_at"))
    cycle_id = str(payload.get("cycle_id"))
    recovery = db.scalar(
        select(RecoveryScore).where(
            RecoveryScore.user_id == user_id,
            RecoveryScore.provider == "WHOOP",
            RecoveryScore.cycle_id == cycle_id,
        )
    )
    if not recovery:
        recovery = RecoveryScore(user_id=user_id, provider="WHOOP", cycle_id=cycle_id, score_date=day)
    recovery.recovery_score = score.get("recovery_score")
    recovery.resting_heart_rate = score.get("resting_heart_rate")
    recovery.hrv_ms = score.get("hrv_rmssd_milli")
    recovery.raw_json = dump_raw(payload)
    db.add(recovery)

    summary = _get_summary(db, user_id, day)
    summary.recovery_score = recovery.recovery_score
    summary.resting_heart_rate = recovery.resting_heart_rate
    summary.hrv_ms = recovery.hrv_ms
    summary.raw_json = dump_raw(payload)
    db.add(summary)
    return recovery


def _get_summary(db: Session, user_id: int, day) -> DailySummary:
    summary = db.scalar(select(DailySummary).where(DailySummary.user_id == user_id, DailySummary.summary_date == day))
    if not summary:
        summary = DailySummary(user_id=user_id, summary_date=day, provider="WHOOP")
    return summary

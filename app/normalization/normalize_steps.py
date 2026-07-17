from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailySummary


def upsert_steps(db: Session, user_id: int, provider: str, summary_date: date, steps: int) -> DailySummary:
    summary = db.scalar(select(DailySummary).where(DailySummary.user_id == user_id, DailySummary.summary_date == summary_date))
    if not summary:
        summary = DailySummary(user_id=user_id, summary_date=summary_date, provider=provider)
    summary.steps = steps
    db.add(summary)
    return summary

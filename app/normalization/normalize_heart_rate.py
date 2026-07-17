from datetime import datetime

from sqlalchemy.orm import Session

from app.models import HeartRateSample


def add_heart_rate_sample(db: Session, user_id: int, provider: str, sampled_at: datetime, bpm: float, context: str | None = None) -> HeartRateSample:
    sample = HeartRateSample(user_id=user_id, provider=provider, sampled_at=sampled_at, bpm=bpm, context=context)
    db.add(sample)
    return sample

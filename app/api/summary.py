from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.ai.daily_decision_engine import build_or_get_daily_briefing
from app.database import get_db
from app.dependencies import get_current_user
from app.models import AiDailyBriefing, BodyMetric, DailySummary, HeartRateSample, RecoveryScore, SleepSession, User, Workout
from app.schemas import DecisionBriefing, SummaryResponse

router = APIRouter()


@router.get("/summary/today", response_model=SummaryResponse)
def summary_today(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DailySummary:
    return _summary_for(date.today(), user.id, db)


@router.get("/summary/yesterday", response_model=SummaryResponse)
def summary_yesterday(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DailySummary:
    return _summary_for(date.today() - timedelta(days=1), user.id, db)


@router.get("/sleep", response_model=None)
def sleep(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SleepSession]:
    return list(db.scalars(select(SleepSession).where(SleepSession.user_id == user.id).order_by(desc(SleepSession.start_time))).all())


@router.get("/recovery", response_model=None)
def recovery(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[RecoveryScore]:
    return list(db.scalars(select(RecoveryScore).where(RecoveryScore.user_id == user.id).order_by(desc(RecoveryScore.score_date))).all())


@router.get("/workouts", response_model=None)
def workouts(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Workout]:
    return list(db.scalars(select(Workout).where(Workout.user_id == user.id).order_by(desc(Workout.start_time))).all())


@router.get("/heart-rate", response_model=None)
def heart_rate(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[HeartRateSample]:
    return list(db.scalars(select(HeartRateSample).where(HeartRateSample.user_id == user.id).order_by(desc(HeartRateSample.sampled_at)).limit(1000)).all())


@router.get("/body-metrics", response_model=None)
def body_metrics(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[BodyMetric]:
    return list(db.scalars(select(BodyMetric).where(BodyMetric.user_id == user.id).order_by(desc(BodyMetric.sampled_at)).limit(1000)).all())


@router.get("/decision/today", response_model=DecisionBriefing)
async def decision_today(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    return await build_or_get_daily_briefing(db, user.id, date.today())


@router.delete("/me/data")
def delete_my_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    for model in [AiDailyBriefing, DailySummary, SleepSession, Workout, HeartRateSample, BodyMetric, RecoveryScore]:
        for row in db.scalars(select(model).where(model.user_id == user.id)).all():
            db.delete(row)
    db.commit()
    return {"status": "deleted"}


def _summary_for(summary_date: date, user_id: int, db: Session) -> DailySummary:
    summary = db.scalar(select(DailySummary).where(DailySummary.user_id == user_id, DailySummary.summary_date == summary_date))
    if not summary:
        raise HTTPException(status_code=404, detail="No summary found for that date")
    return summary

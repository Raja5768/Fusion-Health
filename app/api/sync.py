from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.connectors.whoop_connector import WhoopConnector
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import SyncResponse

router = APIRouter()


@router.post("/whoop", response_model=SyncResponse)
async def sync_whoop(days: int = 14, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SyncResponse:
    result = await WhoopConnector().sync_user(db, user.id, days=days)
    return SyncResponse(provider="WHOOP", synced_at=datetime.utcnow(), **result)

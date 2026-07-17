from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.normalization.normalize_apple_health import import_apple_health_payload
from app.schemas import AppleHealthImport

router = APIRouter()


@router.post("/apple-health")
def import_apple_health(
    payload: AppleHealthImport,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    counts = import_apple_health_payload(db, user.id, payload.model_dump())
    return {"provider": "Apple Health", "imported": counts, "imported_at": datetime.utcnow()}

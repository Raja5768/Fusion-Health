from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import ApiKey, User
from app.schemas import ApiKeyCreate
from app.security import generate_api_key

router = APIRouter()


@router.get("")
def list_api_keys(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    keys = db.scalars(select(ApiKey).where(ApiKey.user_id == user.id, ApiKey.revoked_at.is_(None))).all()
    return [{"id": key.id, "name": key.name, "prefix": key.prefix, "created_at": key.created_at} for key in keys]


@router.post("/generate")
def generate_key(
    payload: ApiKeyCreate = ApiKeyCreate(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    raw, prefix, key_hash = generate_api_key()
    api_key = ApiKey(user_id=user.id, name=payload.name, prefix=prefix, key_hash=key_hash)
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return {"id": api_key.id, "name": api_key.name, "api_key": raw, "prefix": prefix}


@router.delete("/{key_id}")
def delete_key(key_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    api_key = db.get(ApiKey, key_id)
    if not api_key or api_key.user_id != user.id:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key.revoked_at = datetime.utcnow()
    db.commit()
    return {"status": "revoked"}

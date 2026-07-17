import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.connectors.whoop_connector import WhoopConnector
from app.database import get_db
from app.dependencies import get_current_user
from app.models import OAuthState, Provider, ProviderToken, User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.security import create_local_token, encrypt_value, hash_password, token_expiry, verify_password

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=payload.email, full_name=payload.full_name, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_local_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(access_token=create_local_token(user.id))


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict[str, object]:
    return {"id": user.id, "email": user.email, "full_name": user.full_name}


@router.get("/whoop/connect")
def whoop_connect(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    settings = get_settings()
    if not settings.whoop_client_id:
        raise HTTPException(status_code=400, detail="WHOOP_CLIENT_ID is not configured")
    state = secrets.token_urlsafe(6)[:8]
    db.add(OAuthState(state=state, user_id=user.id, provider="whoop"))
    db.commit()
    params = {
        "response_type": "code",
        "client_id": settings.whoop_client_id,
        "redirect_uri": settings.whoop_redirect_uri,
        "scope": settings.whoop_scopes,
        "state": state,
    }
    return {"auth_url": f"{WhoopConnector.AUTH_URL}?{urlencode(params)}"}


@router.get("/whoop/callback", response_class=HTMLResponse)
async def whoop_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> str:
    oauth_state = db.get(OAuthState, state)
    if not oauth_state or oauth_state.provider != "whoop":
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    if oauth_state.created_at < datetime.utcnow() - timedelta(minutes=15):
        raise HTTPException(status_code=400, detail="OAuth state expired")

    connector = WhoopConnector()
    token = await connector.exchange_code(code)
    provider = db.scalar(select(Provider).where(Provider.name == "whoop"))
    if not provider:
        raise HTTPException(status_code=500, detail="WHOOP provider is missing")

    existing = db.scalar(
        select(ProviderToken).where(
            ProviderToken.user_id == oauth_state.user_id,
            ProviderToken.provider_id == provider.id,
        )
    )
    record = existing or ProviderToken(user_id=oauth_state.user_id, provider_id=provider.id)
    record.access_token_encrypted = encrypt_value(token["access_token"]) or ""
    record.refresh_token_encrypted = encrypt_value(token.get("refresh_token"))
    record.expires_at = token_expiry(token.get("expires_in"))
    record.scope = token.get("scope")
    db.add(record)
    db.delete(oauth_state)
    db.commit()
    return "<h1>WHOOP connected</h1><p>You can close this tab and return to Fusion Health.</p>"

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta

from cryptography.fernet import Fernet
from passlib.context import CryptContext

from app.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _sign(payload: str) -> str:
    key = get_settings().secret_key.encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def create_local_token(user_id: int, expires_hours: int = 24) -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + expires_hours * 3600}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return f"{body}.{_sign(body)}"


def verify_local_token(token: str) -> int | None:
    try:
        body, signature = token.rsplit(".", 1)
        if not hmac.compare_digest(_sign(body), signature):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body.encode()).decode())
        if payload["exp"] < time.time():
            return None
        return int(payload["sub"])
    except Exception:
        return None


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    raw = f"fh_{secrets.token_urlsafe(32)}"
    return raw, raw[:10], hash_api_key(raw)


def encrypt_value(value: str | None) -> str | None:
    if value is None:
        return None
    return _fernet().encrypt(value.encode()).decode()


def decrypt_value(value: str | None) -> str | None:
    if value is None:
        return None
    return _fernet().decrypt(value.encode()).decode()


def token_expiry(expires_in: int | None) -> datetime | None:
    if not expires_in:
        return None
    return datetime.utcnow() + timedelta(seconds=max(0, expires_in - 60))


def _fernet() -> Fernet:
    settings = get_settings()
    if settings.fusion_encryption_key:
        key = settings.fusion_encryption_key.encode()
    else:
        digest = hashlib.sha256(settings.secret_key.encode()).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)

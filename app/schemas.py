from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ApiKeyCreate(BaseModel):
    name: str = "Default key"


class AppleHealthImport(BaseModel):
    steps: list[dict[str, Any]] = []
    sleep: list[dict[str, Any]] = []
    heart_rate: list[dict[str, Any]] = []
    workouts: list[dict[str, Any]] = []
    calories: list[dict[str, Any]] = []
    body_metrics: list[dict[str, Any]] = []


class DecisionBriefing(BaseModel):
    readiness_score: int
    decision: str
    why: list[str]
    recommended_actions: list[str]
    data_sources: list[str]


class SyncResponse(BaseModel):
    provider: str
    cycles: int = 0
    sleep_sessions: int = 0
    recoveries: int = 0
    workouts: int = 0
    heart_rate_samples: int = 0
    synced_at: datetime


class SummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    summary_date: date
    sleep_hours: float | None = None
    recovery_score: float | None = None
    strain: float | None = None
    resting_heart_rate: float | None = None
    hrv_ms: float | None = None
    steps: int | None = None
    calories: float | None = None
    provider: str | None = None

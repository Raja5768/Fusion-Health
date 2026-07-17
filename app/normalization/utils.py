import json
from datetime import date, datetime
from typing import Any


def dump_raw(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), default=str)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def parse_day(value: str | None) -> date:
    parsed = parse_dt(value)
    return parsed.date() if parsed else date.today()

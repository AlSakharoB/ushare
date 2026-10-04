import hashlib
import hmac
import json
import re
from datetime import datetime
from urllib.parse import parse_qsl

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from receiptsplit.api.errors import AppError


class TelegramUser(BaseModel):
    model_config = ConfigDict(strict=True)
    id: int = Field(gt=0, lt=2**52)
    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(default="", max_length=128)
    username: str | None = Field(default=None, max_length=64)


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def validate_init_data(raw: str, token: str, now: datetime) -> TelegramUser:
    try:
        if not token or len(raw) > 16384 or re.search(r"%(?![0-9a-fA-F]{2})", raw):
            raise ValueError("invalid encoding/config")
        pairs = parse_qsl(
            raw,
            keep_blank_values=True,
            strict_parsing=True,
            encoding="utf-8",
            errors="strict",
            max_num_fields=32,
        )
        fields = dict(pairs)
        if len(fields) != len(pairs):
            raise ValueError("duplicate parameters")
        digest = fields.pop("hash")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise ValueError("invalid hash")
        # HMAC method excludes only hash. signature remains a signed field.
        data = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
        secret = hmac.digest(b"WebAppData", token.encode(), "sha256")
        expected = hmac.new(secret, data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, digest.lower()):
            raise ValueError("invalid signature")
        if not re.fullmatch(r"[0-9]{1,12}", fields["auth_date"]):
            raise ValueError("invalid date")
        age = now.timestamp() - int(fields["auth_date"])
        if age > 600 or age < -30:
            raise ValueError("expired date")
        return TelegramUser.model_validate(
            json.loads(fields["user"], object_pairs_hook=unique_object)
        )
    except (KeyError, ValueError, UnicodeError, ValidationError) as exc:
        raise AppError(
            "invalid_init_data", "Откройте приложение заново через Telegram", 401
        ) from exc

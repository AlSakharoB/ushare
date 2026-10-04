from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from receiptsplit.api.errors import AppError
from receiptsplit.auth.telegram import validate_init_data
from receiptsplit.config import Settings

TOKEN = "12345:test-token"
NOW = datetime.fromtimestamp(1791072000, UTC)
FIXTURE = (Path(__file__).parent / "fixtures/telegram_init_data.txt").read_text().strip()


def test_independent_node_signed_fixture_with_signature_and_unicode() -> None:
    user = validate_init_data(FIXTURE, TOKEN, NOW)
    assert user.id == 900000000001
    assert user.first_name == "Алёна"


@pytest.mark.parametrize(
    "raw",
    [
        FIXTURE.replace("900000000001", "900000000002"),
        FIXTURE + "&auth_date=1791072000",
        FIXTURE + "&user=%7B%7D",
        FIXTURE.replace("hash=", "bad="),
        "user=%FF",
        "user=%GG",
        "hash=xyz",
    ],
)
def test_tampering_duplicates_and_encoding_rejected(raw: str) -> None:
    with pytest.raises(AppError) as error:
        validate_init_data(raw, TOKEN, NOW)
    assert error.value.status == 401


@pytest.mark.parametrize("offset", [601, -31])
def test_freshness(offset: int) -> None:
    with pytest.raises(AppError):
        validate_init_data(FIXTURE, TOKEN, NOW + timedelta(seconds=offset))


def test_explicit_freshness_boundaries() -> None:
    assert validate_init_data(FIXTURE, TOKEN, NOW + timedelta(seconds=600)).id
    assert validate_init_data(FIXTURE, TOKEN, NOW - timedelta(seconds=30)).id


def test_production_dev_auth_and_http_origin_fail_fast() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", dev_auth_enabled=True, public_origin="https://test.invalid")
    with pytest.raises(ValidationError):
        Settings(app_env="production", public_origin="http://test.invalid")

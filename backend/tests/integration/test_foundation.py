import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from receiptsplit.api.app import create_app
from receiptsplit.config import Settings
from receiptsplit.db.session import build_engine, transaction

pytestmark = pytest.mark.integration


def test_readiness_and_transaction_rollback() -> None:
    settings = Settings()
    engine = build_engine(settings.database_url)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/ready").status_code == 200
    with pytest.raises(RuntimeError), transaction(engine) as session:
        session.execute(text("CREATE TABLE foundation_rollback (id integer)"))
        raise RuntimeError("rollback")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT to_regclass('foundation_rollback')")) is None

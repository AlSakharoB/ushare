from fastapi.testclient import TestClient

from receiptsplit.api.app import create_app
from receiptsplit.config import Settings


def test_liveness_does_not_require_database() -> None:
    with TestClient(
        create_app(
            Settings(database_url="postgresql+psycopg://invalid:invalid@localhost:1/missing")
        )
    ) as client:
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.headers["x-request-id"]
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/health/ready").status_code == 503

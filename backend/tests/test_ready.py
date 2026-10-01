import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database.session import get_session
from app.main import app

client = TestClient(app)


class BrokenSession:
    def execute(self, *args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def test_ready_returns_503_when_database_down():
    app.dependency_overrides[get_session] = lambda: BrokenSession()
    try:
        response = client.get("/api/v1/ready")
        assert response.status_code == 503
        assert response.json()["database"] == "unreachable"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
def test_ready_returns_200_with_database():
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

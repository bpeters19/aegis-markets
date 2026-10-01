from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_bars_rejects_timestamps_without_timezone():
    response = client.get(
        "/api/v1/bars",
        params={"symbol": "NVDA", "timeframe": "1Day",
                "start": "2026-01-01T00:00:00", "end": "2026-01-10T00:00:00"},
    )
    assert response.status_code == 422


def test_bars_rejects_start_after_end():
    response = client.get(
        "/api/v1/bars",
        params={"symbol": "NVDA", "timeframe": "1Day",
                "start": "2026-01-10T00:00:00Z", "end": "2026-01-01T00:00:00Z"},
    )
    assert response.status_code == 422

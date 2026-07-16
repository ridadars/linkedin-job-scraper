"""Health endpoint tests."""

def test_health_endpoint_returns_ok(client) -> None:
    """Health check should report application and database status."""
    response = client.get("/api/health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert payload["app_name"] == "LinkedIn Job Scraper"
    assert "timestamp" in payload
    assert payload["database"] in {"connected", "disconnected"}


def test_health_endpoint_database_connected(client) -> None:
    """Database should be reachable after application startup."""
    response = client.get("/api/health")
    payload = response.json()
    assert payload["database"] == "connected"

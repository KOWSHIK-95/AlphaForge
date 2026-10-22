from fastapi.testclient import TestClient

from alphaforge.api.app import app


def test_stable_production_origin_is_allowed():
    response = TestClient(app).options(
        "/health",
        headers={
            "Origin": "https://alpha-forge-bice.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://alpha-forge-bice.vercel.app"


def test_unrelated_origin_is_rejected():
    response = TestClient(app).options(
        "/health",
        headers={
            "Origin": "https://unrelated.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers

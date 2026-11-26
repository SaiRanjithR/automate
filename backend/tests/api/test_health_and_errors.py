from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import ConflictError, NotFoundError


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_domain_error_maps_to_error_shape(app: FastAPI) -> None:
    @app.get("/api/_test/missing")
    def missing() -> None:
        raise NotFoundError("Project 12 not found")

    @app.get("/api/_test/conflict")
    def conflict() -> None:
        raise ConflictError("Already approved")

    with TestClient(app) as client:
        not_found = client.get("/api/_test/missing")
        assert not_found.status_code == 404
        assert not_found.json() == {
            "error": {"code": "not_found", "message": "Project 12 not found"}
        }
        assert client.get("/api/_test/conflict").json()["error"]["code"] == "conflict"


def test_unknown_route_uses_error_shape(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_unhandled_exception_hides_details(app: FastAPI) -> None:
    @app.get("/api/_test/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/_test/boom")
        assert response.status_code == 500
        assert response.json() == {"error": {"code": "internal", "message": "Something went wrong"}}


def test_request_validation_error_shape(app: FastAPI) -> None:
    @app.get("/api/_test/items/{item_id}")
    def item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    with TestClient(app) as client:
        response = client.get("/api/_test/items/not-a-number")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_failed"

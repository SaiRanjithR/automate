from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Isolated settings: temp data dirs, no .env file, no real API key."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]  # pydantic-settings init kwarg not in signature
        app_env="test",
        data_dir=tmp_path / "data",
        files_dir=tmp_path / "data" / "files",
        policy_dir=tmp_path / "policies",
        database_url=f"sqlite:///{tmp_path / 'data' / 'app.db'}",
        anthropic_api_key=None,
        llm_provider="offline",
        embedding_provider="hash",
        jobs_inline=True,
        admin_email="admin@example.com",
        admin_password="test-password",
    )


@pytest.fixture
def app(test_settings: Settings) -> FastAPI:
    return create_app(test_settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


SAMPLES = Path(__file__).resolve().parents[2] / "samples"


@pytest.fixture
def auth_client(client: TestClient) -> TestClient:
    response = client.post(
        "/api/auth/login", json={"email": "admin@example.com", "password": "test-password"}
    )
    assert response.status_code == 200, response.text
    return client

from pathlib import Path

from app.core.config import REPO_ROOT, Settings


def test_relative_paths_resolve_against_repo_root() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        data_dir=Path("./backend/data"),
        database_url="sqlite:///./backend/data/app.db",
    )
    assert settings.data_dir == (REPO_ROOT / "backend" / "data").resolve()
    assert (
        settings.resolved_database_url
        == f"sqlite:///{(REPO_ROOT / 'backend/data/app.db').resolve()}"
    )


def test_empty_api_key_is_none() -> None:
    settings = Settings(_env_file=None, anthropic_api_key="")  # type: ignore[call-arg]
    assert settings.anthropic_api_key is None


def test_cors_origin_list_splits_and_trims() -> None:
    settings = Settings(_env_file=None, cors_origins="http://a.test, http://b.test ,")  # type: ignore[call-arg]
    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]

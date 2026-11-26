"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlmodel import Session

from app.core.config import Settings
from app.core.db import get_session
from app.core.errors import UnauthorizedError
from app.core.security import SESSION_COOKIE, decode_token
from app.models import User


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def current_user(
    session: SessionDep,
    settings: SettingsDep,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    if not token:
        raise UnauthorizedError("Sign in required")
    user = session.get(User, decode_token(token, settings))
    if user is None or not user.is_active:
        raise UnauthorizedError("Sign in required")
    return user


CurrentUser = Annotated[User, Depends(current_user)]

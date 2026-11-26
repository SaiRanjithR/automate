from fastapi import APIRouter, Request, Response
from sqlmodel import select

from app.core.deps import CurrentUser, SessionDep, SettingsDep
from app.core.errors import UnauthorizedError
from app.core.security import SESSION_COOKIE, create_token, verify_password
from app.models import User
from app.schemas.api import LoginRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _out(user: User) -> UserOut:
    assert user.id is not None
    return UserOut(id=user.id, email=user.email, name=user.name)


@router.post("/login", response_model=UserOut)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> UserOut:
    user = session.exec(select(User).where(User.email == body.email.strip().lower())).first()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise UnauthorizedError("Email or password is incorrect")
    assert user.id is not None
    response.set_cookie(
        SESSION_COOKIE,
        create_token(user.id, settings),
        httponly=True,
        samesite="lax",
        # Secure only over https, so a plain-http LAN demo still works
        secure=request.url.scheme == "https",
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )
    return _out(user)


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return _out(user)

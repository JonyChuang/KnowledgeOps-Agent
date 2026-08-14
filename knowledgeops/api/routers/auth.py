"""Registration, login, logout, and administrator account management APIs."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import Settings
from ...models import AuthSession, User, UserRole
from ...schemas import (
    AuthenticatedUserRead,
    PasswordChangeCreate,
    UserLoginCreate,
    UserProfileUpdate,
    UserRead,
    UserRegisterCreate,
    UserRoleUpdate,
)
from ...security import SESSION_COOKIE_NAME, create_access_token, hash_password, utc_now, verify_password
from ..dependencies import get_current_principal, get_session, get_settings, require_admin

auth_router = APIRouter(prefix="/auth", tags=["authentication"])


def _set_access_cookie(response: Response, token: str, expires_in_seconds: int, settings: Settings) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=expires_in_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


async def _create_login_response(
    *, user: User, session: AsyncSession, response: Response, settings: Settings
) -> AuthenticatedUserRead:
    now = utc_now()
    session_record = AuthSession(
        user_id=user.id,
        expires_at=now + timedelta(seconds=settings.auth_access_token_ttl_seconds),
    )
    session.add(session_record)
    await session.flush()
    token, expires_at = create_access_token(
        user_id=user.id,
        session_id=session_record.id,
        secret=settings.auth_jwt_secret.get_secret_value(),
        expires_in_seconds=settings.auth_access_token_ttl_seconds,
    )
    _set_access_cookie(response, token, settings.auth_access_token_ttl_seconds, settings)
    await session.commit()
    return AuthenticatedUserRead(user=UserRead.model_validate(user), expires_at=expires_at)


@auth_router.post("/register", response_model=AuthenticatedUserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegisterCreate,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUserRead:
    """Create an account; bootstrap the first account as the platform administrator."""
    existing = await session.scalar(select(User.id).where(User.username == payload.username))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This username is already in use.")
    user_count = await session.scalar(select(func.count()).select_from(User))
    user = User(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role=UserRole.ADMIN if user_count == 0 else UserRole.EMPLOYEE,
    )
    session.add(user)
    await session.flush()
    return await _create_login_response(user=user, session=session, response=response, settings=settings)


@auth_router.post("/login", response_model=AuthenticatedUserRead)
async def login(
    payload: UserLoginCreate,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUserRead:
    """Authenticate an active account and issue a revocable HttpOnly session cookie."""
    user = await session.scalar(select(User).where(User.username == payload.username))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password.")
    return await _create_login_response(user=user, session=session, response=response, settings=settings)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    principal=Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Revoke the current session server-side, then remove its browser cookie."""
    session_record = await session.get(AuthSession, principal.session_id)
    if session_record is not None and session_record.revoked_at is None:
        session_record.revoked_at = utc_now()
        await session.commit()
    response.delete_cookie(SESSION_COOKIE_NAME, path="/", secure=settings.auth_cookie_secure, samesite="lax")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@auth_router.get("/me", response_model=AuthenticatedUserRead)
async def me(principal=Depends(get_current_principal)) -> AuthenticatedUserRead:
    """Return the active session user for application bootstrap."""
    return AuthenticatedUserRead(user=UserRead.model_validate(principal.user), expires_at=principal.expires_at)


@auth_router.patch("/me", response_model=UserRead)
async def update_profile(
    payload: UserProfileUpdate,
    principal=Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    """Let a signed-in user update only their own public display name."""
    principal.user.display_name = payload.display_name
    await session.commit()
    await session.refresh(principal.user)
    return UserRead.model_validate(principal.user)


@auth_router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChangeCreate,
    principal=Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Verify the existing password before replacing its server-side hash."""
    if not verify_password(payload.current_password, principal.user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
    if verify_password(payload.new_password, principal.user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be different.")
    principal.user.password_hash = hash_password(payload.new_password)
    await session.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == principal.user.id,
            AuthSession.id != principal.session_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=utc_now())
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@auth_router.get("/users", response_model=list[UserRead])
async def list_users(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> list[UserRead]:
    """Let administrators inspect accounts when assigning workspace roles."""
    users = (await session.scalars(select(User).order_by(User.created_at.asc()))).all()
    return [UserRead.model_validate(user) for user in users]


@auth_router.patch("/users/{user_id}/role", response_model=UserRead)
async def update_user_role(
    user_id: str,
    payload: UserRoleUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> UserRead:
    """Assign employee, service-desk, or administrator permissions server-side."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User was not found.")
    user.role = payload.role
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)

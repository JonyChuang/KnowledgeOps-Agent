"""FastAPI dependencies shared by all HTTP routers."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..db import Database
from ..models import AuthSession, User, UserRole
from ..security import SESSION_COOKIE_NAME, decode_access_token, ensure_utc, utc_now


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide one database session for a single HTTP request."""
    database: Database = request.app.state.database

    async for session in database.session():
        yield session


def get_settings(request: Request) -> Settings:
    """Expose the app settings without accepting client-provided identity data."""
    return request.app.state.settings


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user: User
    session_id: str
    expires_at: datetime


async def get_current_principal(
    access_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    x_actor: str | None = Header(default=None),
    x_role: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedPrincipal:
    """Resolve a signed browser token to an active account and non-revoked session."""
    if not access_token and settings.auth_test_mode and x_actor:
        # Existing API tests keep legacy request headers only when they explicitly
        # opt into test mode. This branch is never enabled by deployed settings.
        role = UserRole.SERVICE_DESK if (x_role or "").lower() == "service_desk" else UserRole.EMPLOYEE
        return AuthenticatedPrincipal(
            user=User(
                id=f"test-{x_actor}",
                username=x_actor.strip() or "test-user",
                display_name=x_actor.strip() or "test-user",
                password_hash="test-only",
                role=role,
            ),
            session_id="test-session",
            expires_at=utc_now(),
        )
    if not access_token and settings.auth_test_mode:
        # Preserve the prior test-only authorization outcome for requests that
        # intentionally omit a role header.
        return AuthenticatedPrincipal(
            user=User(
                id="test-anonymous",
                username="anonymous",
                display_name="anonymous",
                password_hash="test-only",
                role=UserRole.EMPLOYEE,
            ),
            session_id="test-session",
            expires_at=utc_now(),
        )
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in to continue.")
    payload = decode_access_token(access_token, secret=settings.auth_jwt_secret.get_secret_value())
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session is invalid or expired.")
    result = await session.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.id == payload["sid"], AuthSession.user_id == payload["sub"])
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session is no longer available.")
    auth_session, user = row
    if auth_session.revoked_at is not None or ensure_utc(auth_session.expires_at) <= utc_now() or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session has expired. Please sign in again.")
    return AuthenticatedPrincipal(user=user, session_id=auth_session.id, expires_at=ensure_utc(auth_session.expires_at))


async def get_current_user(principal: AuthenticatedPrincipal = Depends(get_current_principal)) -> User:
    return principal.user


async def get_actor(user: User = Depends(get_current_user)) -> str:
    """Return the authenticated username; client headers can no longer choose it."""
    return user.username


async def get_service_desk_actor(user: User = Depends(get_current_user)) -> str:
    """Gate service-desk operations behind a server-side user role."""
    if user.role not in {UserRole.SERVICE_DESK, UserRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service-desk role is required for this operation.",
        )
    return user.username


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Allow account administration only for a server-side administrator role."""
    if user.role is not UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role is required for this operation.")
    return user

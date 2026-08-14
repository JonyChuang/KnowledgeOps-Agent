"""Password hashing and compact HS256 JWT helpers without provider coupling."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

PASSWORD_ITERATIONS = 600_000
SESSION_COOKIE_NAME = "knowledgeops_access_token"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    """SQLite may return a naive value for timezone-aware ORM columns."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    """Store passwords with PBKDF2-SHA256, a unique salt, and a work factor."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_base64url_encode(salt)}${_base64url_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, encoded_salt, encoded_digest = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        expected = _base64url_decode(encoded_digest)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _base64url_decode(encoded_salt), int(iterations)
        )
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(actual, expected)


def create_access_token(*, user_id: str, session_id: str, secret: str, expires_in_seconds: int) -> tuple[str, datetime]:
    expires_at = utc_now() + timedelta(seconds=expires_in_seconds)
    payload = {
        "sub": user_id,
        "sid": session_id,
        "iat": int(utc_now().timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    encoded_header = _base64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    encoded_payload = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{_base64url_encode(signature)}", expires_at


def decode_access_token(token: str, *, secret: str) -> dict[str, Any] | None:
    """Verify signature and expiry before returning a minimally validated payload."""
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        header = json.loads(_base64url_decode(encoded_header))
        payload = json.loads(_base64url_decode(encoded_payload))
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if header != {"alg": "HS256", "typ": "JWT"} or not hmac.compare_digest(expected, _base64url_decode(encoded_signature)):
            return None
        if not isinstance(payload.get("sub"), str) or not isinstance(payload.get("sid"), str):
            return None
        if int(payload["exp"]) <= int(utc_now().timestamp()):
            return None
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload

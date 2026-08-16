"""Single-user authentication primitives for the local Newsroom app."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from . import storage


SESSION_COOKIE = "newsroom_session"
CSRF_COOKIE = "newsroom_csrf"
SESSION_TTL = timedelta(hours=24)
LOGIN_WINDOW = timedelta(minutes=15)
LOGIN_LOCKOUT = timedelta(minutes=5)
MAX_LOGIN_FAILURES = 5
USERNAME_PATTERN = r"^[a-z0-9][a-z0-9_.-]{2,63}$"


class AuthError(Exception):
    """Base class for expected authentication failures."""


class SetupUnavailable(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class LoginThrottled(AuthError):
    pass


@dataclass(frozen=True)
class SessionData:
    session_token: str
    csrf_token: str
    username: str


@dataclass(frozen=True)
class AuthenticatedUser:
    session_id: str
    user_id: str
    username: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def normalize_username(username: str) -> str:
    return username.strip().lower()


def _session_record_id(session_token: str) -> str:
    return hashlib.sha256(session_token.encode("ascii")).hexdigest()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


_DUMMY_PASSWORD_HASH = PasswordHasher(type=Type.ID).hash(secrets.token_urlsafe(32))


class AuthService:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.password_hasher = PasswordHasher(type=Type.ID)

    def setup(self, username: str, password: str) -> str:
        username = normalize_username(username)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None:
                    raise SetupUnavailable()
                now = timestamp(utc_now())
                conn.execute(
                    """
                    INSERT INTO users
                        (id, username, password_hash, password_algo, created_at, updated_at)
                    VALUES (?, ?, ?, 'argon2id', ?, ?)
                    """,
                    (
                        f"usr_{secrets.token_hex(16)}",
                        username,
                        self.password_hasher.hash(password),
                        now,
                        now,
                    ),
                )
        finally:
            conn.close()
        return username

    def login(self, username: str, password: str) -> SessionData:
        username = normalize_username(username)
        conn = storage.connect(self.db_path)
        try:
            now = utc_now()
            throttle = conn.execute(
                "SELECT failed_count, first_failed_at, locked_until FROM auth_login_attempts WHERE username = ?",
                (username,),
            ).fetchone()
            if throttle and throttle[2] and throttle[2] > timestamp(now):
                raise LoginThrottled()

            user = conn.execute(
                "SELECT id, username, password_hash, disabled_at FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            valid = False
            hash_to_verify = user[2] if user is not None else _DUMMY_PASSWORD_HASH
            try:
                verified = self.password_hasher.verify(hash_to_verify, password)
                valid = user is not None and user[3] is None and verified
            except (InvalidHashError, VerificationError, VerifyMismatchError):
                valid = False

            if not valid:
                with storage.write_tx(conn):
                    self._record_failure(conn, username, now, throttle)
                    current = conn.execute(
                        "SELECT locked_until FROM auth_login_attempts WHERE username = ?",
                        (username,),
                    ).fetchone()
                if current and current[0] and current[0] > timestamp(now):
                    raise LoginThrottled()
                raise InvalidCredentials()

            with storage.write_tx(conn):
                conn.execute(
                    "DELETE FROM auth_login_attempts WHERE username = ?", (username,)
                )
                session_token = secrets.token_urlsafe(32)
                csrf_token = secrets.token_urlsafe(32)
                created_at = timestamp(now)
                expires_at = timestamp(now + SESSION_TTL)
                conn.execute(
                    """
                    INSERT INTO sessions
                        (id, user_id, created_at, expires_at, csrf_token_hash)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        _session_record_id(session_token),
                        user[0],
                        created_at,
                        expires_at,
                        _token_hash(csrf_token),
                    ),
                )
                return SessionData(session_token, csrf_token, user[1])
        finally:
            conn.close()

    def _record_failure(self, conn, username: str, now: datetime, throttle) -> None:
        if throttle is None:
            failed_count = 1
            first_failed_at = now
        else:
            try:
                first_failed_at = datetime.fromisoformat(
                    throttle[1].replace("Z", "+00:00")
                )
            except (AttributeError, ValueError):
                first_failed_at = now
            if now - first_failed_at > LOGIN_WINDOW:
                failed_count = 1
                first_failed_at = now
            else:
                failed_count = int(throttle[0]) + 1
        locked_until = (
            timestamp(now + LOGIN_LOCKOUT)
            if failed_count >= MAX_LOGIN_FAILURES
            else None
        )
        conn.execute(
            """
            INSERT INTO auth_login_attempts
                (username, failed_count, first_failed_at, locked_until, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                failed_count = excluded.failed_count,
                first_failed_at = excluded.first_failed_at,
                locked_until = excluded.locked_until,
                updated_at = excluded.updated_at
            """,
            (
                username,
                failed_count,
                timestamp(first_failed_at),
                locked_until,
                timestamp(now),
            ),
        )

    def authenticate(self, session_token: Optional[str]) -> Optional[AuthenticatedUser]:
        if not session_token:
            return None
        now = timestamp(utc_now())
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute(
                """
                SELECT sessions.id, users.id, users.username, sessions.csrf_token_hash
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.id = ?
                  AND sessions.expires_at > ?
                  AND sessions.revoked_at IS NULL
                  AND users.disabled_at IS NULL
                """,
                (_session_record_id(session_token), now),
            ).fetchone()
            if row is None:
                return None
            return AuthenticatedUser(row[0], row[1], row[2])
        finally:
            conn.close()

    def valid_csrf(self, session_token: Optional[str], csrf_token: Optional[str], csrf_cookie: Optional[str]) -> bool:
        if not session_token or not csrf_token or not csrf_cookie:
            return False
        if not hmac.compare_digest(csrf_token, csrf_cookie):
            return False
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT csrf_token_hash FROM sessions WHERE id = ? AND revoked_at IS NULL",
                (_session_record_id(session_token),),
            ).fetchone()
            return bool(row and row[0] and hmac.compare_digest(row[0], _token_hash(csrf_token)))
        finally:
            conn.close()

    def revoke(self, session_token: Optional[str]) -> None:
        if not session_token:
            return
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    "UPDATE sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                    (timestamp(utc_now()), _session_record_id(session_token)),
                )
        finally:
            conn.close()

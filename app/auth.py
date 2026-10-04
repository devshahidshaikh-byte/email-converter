
"""
Authentication and authorization helpers for Email Permutation Studio.

This file intentionally contains many comments because it is meant to be
easy to understand and edit.

Security model:
- SQLite stores users, sessions, approved/private emails and audit events.
- Passwords are NEVER stored as plain text. We use hashlib.scrypt + a random salt.
- Login creates a random server-side session token.
- Only a SHA-256 hash of that token is stored in the database.
- The browser receives the raw token in an HttpOnly cookie.
- State-changing authenticated requests also need the session's CSRF token.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request, Response, status

BASE_DIR = Path(__file__).resolve().parent
# Load the project's .env file if it exists. Environment variables already
# set by the operating system still take precedence in python-dotenv.
load_dotenv(BASE_DIR.parent / '.env')
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "emailtool.db")))

ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "arshad.s@igts.io,dev.shahidshaikh@gmail.com").split(",") if e.strip()]
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "pass123")
# Backward-compatible alias: other modules in the existing app import ADMIN_EMAIL.
# Keep it pointing to the first configured administrator.
ADMIN_EMAIL = ADMIN_EMAILS[0] if ADMIN_EMAILS else ""
SESSION_DAYS = int(os.getenv("SESSION_DAYS", "7"))
# In production (Netlify frontend + Render API), the browser must be allowed
# to send the secure session cookie across the two HTTPS sites.
# Set COOKIE_SECURE=true on Render.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
# Keep this switch true for the premium model: only Gmail addresses that the
# administrator has explicitly added can create an account or log in.
REQUIRE_APPROVAL_FOR_APP = os.getenv("REQUIRE_APPROVAL_FOR_APP", "true").lower() == "true"

SESSION_COOKIE = "emailtool_session"
CSRF_HEADER = "X-CSRF-Token"

EMAIL_RE = re.compile(r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@gmail\.com$", re.I)


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def utc_string(value: Optional[datetime] = None) -> str:
    """Store UTC timestamps in a predictable ISO format."""
    return (value or utc_now()).isoformat()


def get_db() -> sqlite3.Connection:
    """
    Open a SQLite connection.

    row_factory lets us use row["email"] instead of row[1], which makes the
    code much easier to read.
    """
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    """Create all authentication tables if they do not already exist."""
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user'
                    CHECK(role IN ('user', 'admin')),
                is_active INTEGER NOT NULL DEFAULT 1,
                is_approved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                last_login_at TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                csrf_token TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS approved_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                added_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(added_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_token_hash
                ON sessions(token_hash);

            CREATE INDEX IF NOT EXISTS idx_audit_created_at
                ON audit_logs(created_at);

            CREATE INDEX IF NOT EXISTS idx_users_email
                ON users(email);
            """
        )

        # Configure all administrator accounts listed in ADMIN_EMAILS.
        # Example: ADMIN_EMAILS=arshad.s@igts.io,dev.shahidshaikh@gmail.com
        password_hash, salt = hash_password(ADMIN_PASSWORD)
        for admin_email in ADMIN_EMAILS:
            existing = db.execute(
                "SELECT id FROM users WHERE email = ?",
                (admin_email,),
            ).fetchone()

            if existing:
                db.execute(
                    """
                    UPDATE users
                    SET role = 'admin', is_active = 1, is_approved = 1
                    WHERE email = ?
                    """,
                    (admin_email,),
                )
            else:
                db.execute(
                    """
                    INSERT INTO users
                        (email, password_hash, password_salt, role,
                         is_active, is_approved, created_at)
                    VALUES (?, ?, ?, 'admin', 1, 1, ?)
                    """,
                    (admin_email, password_hash, salt, utc_string()),
                )


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def is_gmail(email: str) -> bool:
    """The product currently accepts Gmail accounts for user accounts."""
    return bool(EMAIL_RE.fullmatch(normalize_email(email)))


def validate_email(email: str) -> Optional[str]:
    if not normalize_email(email):
        return "Email address is required."
    if not is_gmail(email):
        return "Please use a valid Gmail address ending in @gmail.com."
    return None


def validate_password(password: str) -> Optional[str]:
    if not password:
        return "Password is required."
    if len(password) < 8:
        return "Password must contain at least 8 characters."
    if len(password) > 128:
        return "Password is too long."
    return None


def hash_password(password: str, salt: Optional[bytes] = None) -> tuple[str, str]:
    """
    Derive a strong password hash.

    scrypt is intentionally slow and memory-hard, making password guessing
    much more expensive than hashing with a fast hash such as SHA-256.
    """
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
    )
    return derived.hex(), salt.hex()


def verify_password(password: str, stored_hash: str, stored_salt: str) -> bool:
    try:
        derived, _ = hash_password(password, bytes.fromhex(stored_salt))
        return hmac.compare_digest(derived, stored_hash)
    except (ValueError, TypeError):
        return False


def hash_session_token(token: str) -> str:
    """Only the SHA-256 hash of a session token is stored in SQLite."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def audit(
    db: sqlite3.Connection,
    event: str,
    user_id: Optional[int] = None,
    details: str = "",
    request: Optional[Request] = None,
) -> None:
    """Write a security/activity event for the admin dashboard."""
    ip = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent", "")[:500] if request else ""
    db.execute(
        """
        INSERT INTO audit_logs
            (user_id, event, details, ip_address, user_agent, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, event, details[:1000], ip, user_agent, utc_string()),
    )


def create_session(
    db: sqlite3.Connection,
    user_id: int,
    request: Request,
) -> tuple[str, str]:
    """Create a new random login session and return token + CSRF token."""
    raw_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    now = utc_now()
    expires = now + timedelta(days=SESSION_DAYS)

    db.execute(
        """
        INSERT INTO sessions
            (user_id, token_hash, csrf_token, created_at, expires_at,
             last_seen_at, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            hash_session_token(raw_token),
            csrf_token,
            utc_string(now),
            utc_string(expires),
            utc_string(now),
            request.client.host if request.client else None,
            request.headers.get("user-agent", "")[:500],
        ),
    )
    return raw_token, csrf_token


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=COOKIE_SECURE,
        # Netlify and Render are different origins. "none" is required when
        # COOKIE_SECURE=true so the browser can send the session cookie to API calls.
        samesite="none" if COOKIE_SECURE else "lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def get_current_user(request: Request) -> Optional[sqlite3.Row]:
    """Return the currently logged-in active user, or None."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None

    token_hash = hash_session_token(token)

    with get_db() as db:
        row = db.execute(
            """
            SELECT
                u.*,
                s.id AS session_id,
                s.csrf_token,
                s.expires_at
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ?
              AND u.is_active = 1
            """,
            (token_hash,),
        ).fetchone()

        if not row:
            return None

        try:
            expires = datetime.fromisoformat(row["expires_at"])
        except ValueError:
            return None

        if expires <= utc_now():
            db.execute("DELETE FROM sessions WHERE id = ?", (row["session_id"],))
            return None

        db.execute(
            "UPDATE sessions SET last_seen_at = ? WHERE id = ?",
            (utc_string(), row["session_id"]),
        )
        return row


def require_user(request: Request) -> sqlite3.Row:
    """FastAPI dependency/helper for any logged-in user."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You must be logged in.",
        )

    if REQUIRE_APPROVAL_FOR_APP and user["role"] != "admin" and not user["is_approved"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is waiting for admin approval.",
        )

    return user


def require_admin(request: Request) -> sqlite3.Row:
    """Only an active admin can call admin endpoints."""
    user = require_user(request)
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return user


def require_csrf(request: Request, user: sqlite3.Row) -> None:
    """
    Protect cookie-authenticated state-changing requests.

    A stolen cross-site request cannot normally know this random header value.
    """
    supplied = request.headers.get(CSRF_HEADER, "")
    if not supplied or not hmac.compare_digest(supplied, user["csrf_token"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token.",
        )


def user_has_private_access(user: sqlite3.Row) -> bool:
    """Admins always have private access; selected Gmail users can be approved."""
    return bool(user["role"] == "admin" or user["is_approved"])


def cleanup_expired_sessions(db: sqlite3.Connection) -> None:
    db.execute(
        "DELETE FROM sessions WHERE expires_at <= ?",
        (utc_string(),),
    )

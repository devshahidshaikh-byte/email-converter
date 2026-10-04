
"""Authentication, account and admin API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.auth import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    REQUIRE_APPROVAL_FOR_APP,
    SESSION_COOKIE,
    audit,
    clear_session_cookie,
    create_session,
    get_current_user,
    get_db,
    init_db,
    is_gmail,
    normalize_email,
    require_admin,
    require_csrf,
    require_user,
    set_session_cookie,
    user_has_private_access,
    utc_string,
    validate_email,
    validate_password,
    verify_password,
    hash_password,
    hash_session_token,
)

router = APIRouter(prefix="/api")


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class EmailRequest(BaseModel):
    email: str


class AdminAccountUpdate(BaseModel):
    email: str
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


def public_user(row):
    """Return only fields safe for the browser."""
    return {
        "id": row["id"],
        "email": row["email"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "is_approved": bool(row["is_approved"]),
        "private_access": user_has_private_access(row),
        "created_at": row["created_at"],
        "last_login_at": row["last_login_at"],
    }


@router.post("/auth/register")
def register(payload: RegisterRequest, request: Request, response: Response):
    email = normalize_email(payload.email)
    email_error = validate_email(email)
    password_error = validate_password(payload.password)

    if email_error:
        raise HTTPException(status_code=422, detail=email_error)
    if password_error:
        raise HTTPException(status_code=422, detail=password_error)

    # Prevent accidental creation of another account using the configured
    # administrator address.
    if email == ADMIN_EMAIL:
        raise HTTPException(
            status_code=409,
            detail="That email is reserved for the administrator.",
        )

    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        if existing:
            raise HTTPException(
                status_code=409,
                detail="An account with this Gmail address already exists.",
            )

        password_hash, salt = hash_password(payload.password)

        # Premium access rule:
        # A normal user may NOT create an account unless the administrator
        # has already added that exact Gmail address to the allowlist.
        approved = db.execute(
            "SELECT id FROM approved_emails WHERE email = ?",
            (email,),
        ).fetchone()

        if REQUIRE_APPROVAL_FOR_APP and not approved:
            audit(db, "REGISTER_BLOCKED", None, f"email_not_preapproved={email}", request)
            raise HTTPException(
                status_code=403,
                detail="This Gmail address has not been approved by the administrator yet.",
            )

        cursor = db.execute(
            """
            INSERT INTO users
                (email, password_hash, password_salt, role,
                 is_active, is_approved, created_at)
            VALUES (?, ?, ?, 'user', 1, ?, ?)
            """,
            (
                email,
                password_hash,
                salt,
                1 if approved else 0,
                utc_string(),
            ),
        )
        user_id = cursor.lastrowid

        audit(db, "REGISTER", user_id, f"email={email}", request)

        token, csrf = create_session(db, user_id, request)
        audit(db, "LOGIN_SUCCESS", user_id, "login_after_registration", request)

        user = db.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    set_session_cookie(response, token)
    return {
        "success": True,
        "user": public_user(user),
        "csrf_token": csrf,
        "message": (
            "Account created. Private access is enabled."
            if user["is_approved"]
            else "Account created. Private access can be enabled by an administrator."
        ),
    }


@router.post("/auth/login")
def login(payload: LoginRequest, request: Request, response: Response):
    email = normalize_email(payload.email)

    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        # Deliberately use one generic error for wrong email/password.
        # This avoids revealing whether a particular account exists.
        if not user or not verify_password(
            payload.password,
            user["password_hash"],
            user["password_salt"],
        ):
            if user:
                audit(db, "LOGIN_FAILED", user["id"], "invalid_password", request)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        if not user["is_active"]:
            audit(db, "LOGIN_BLOCKED", user["id"], "account_disabled", request)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account has been disabled by an administrator.",
            )

        # Premium access rule:
        # The administrator must have explicitly approved the Gmail address.
        # This check happens on the SERVER, so changing JavaScript cannot bypass it.
        if (
            REQUIRE_APPROVAL_FOR_APP
            and user["role"] != "admin"
            and not user["is_approved"]
        ):
            audit(db, "LOGIN_BLOCKED", user["id"], "not_preapproved", request)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your Gmail address has not been approved by the administrator.",
            )

        if not is_gmail(email):
            raise HTTPException(
                status_code=422,
                detail="Please use a Gmail account.",
            )

        db.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?",
            (utc_string(), user["id"]),
        )

        token, csrf = create_session(db, user["id"], request)
        audit(db, "LOGIN_SUCCESS", user["id"], "", request)

        user = db.execute(
            "SELECT * FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()

    set_session_cookie(response, token)

    return {
        "success": True,
        "user": public_user(user),
        "csrf_token": csrf,
        "message": "Login successful.",
    }


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    user = get_current_user(request)

    if user:
        require_csrf(request, user)
        with get_db() as db:
            token = request.cookies.get(SESSION_COOKIE)
            if token:
                db.execute(
                    "DELETE FROM sessions WHERE token_hash = ?",
                    (hash_session_token(token),),
                )
            audit(db, "LOGOUT", user["id"], "", request)

    clear_session_cookie(response)
    return {"success": True}


@router.get("/auth/me")
def me(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in.")

    return {
        "success": True,
        "user": public_user(user),
        "csrf_token": user["csrf_token"],
    }


@router.post("/auth/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
):
    user = require_user(request)
    require_csrf(request, user)

    error = validate_password(payload.new_password)
    if error:
        raise HTTPException(status_code=422, detail=error)

    with get_db() as db:
        fresh = db.execute(
            "SELECT * FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()

        if not verify_password(
            payload.current_password,
            fresh["password_hash"],
            fresh["password_salt"],
        ):
            raise HTTPException(
                status_code=400,
                detail="Current password is incorrect.",
            )

        new_hash, new_salt = hash_password(payload.new_password)
        db.execute(
            """
            UPDATE users
            SET password_hash = ?, password_salt = ?
            WHERE id = ?
            """,
            (new_hash, new_salt, user["id"]),
        )

        # Invalidate every other session after a password change.
        current_token = request.cookies.get(SESSION_COOKIE)
        from app.auth import hash_session_token
        current_hash = hash_session_token(current_token) if current_token else ""

        db.execute(
            "DELETE FROM sessions WHERE user_id = ? AND token_hash != ?",
            (user["id"], current_hash),
        )
        audit(db, "PASSWORD_CHANGED", user["id"], "", request)

    return {"success": True, "message": "Password changed successfully."}


# ---------------------------------------------------------------------------
# ADMIN DASHBOARD
# ---------------------------------------------------------------------------

@router.put("/admin/account")
def update_admin_account(payload: AdminAccountUpdate, request: Request):
    """
    Change the administrator's Gmail and/or password.

    This is the recommended way to change the initial development account.
    The initial ADMIN_EMAIL/ADMIN_PASSWORD values are only used when the
    database has no administrator yet.
    """
    admin = require_admin(request)
    require_csrf(request, admin)

    email = normalize_email(payload.email)
    error = validate_email(email)
    if error:
        raise HTTPException(status_code=422, detail=error)

    if payload.new_password:
        password_error = validate_password(payload.new_password)
        if password_error:
            raise HTTPException(status_code=422, detail=password_error)

    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM users WHERE email = ? AND id != ?",
            (email, admin["id"]),
        ).fetchone()

        if existing:
            raise HTTPException(
                status_code=409,
                detail="That Gmail address is already being used by another account.",
            )

        if payload.new_password:
            password_hash, salt = hash_password(payload.new_password)
            db.execute(
                """
                UPDATE users
                SET email = ?, password_hash = ?, password_salt = ?
                WHERE id = ?
                """,
                (email, password_hash, salt, admin["id"]),
            )
        else:
            db.execute(
                "UPDATE users SET email = ? WHERE id = ?",
                (email, admin["id"]),
            )

        audit(
            db,
            "ADMIN_ACCOUNT_UPDATED",
            admin["id"],
            f"email_changed_to={email}; password_changed={bool(payload.new_password)}",
            request,
        )

    return {
        "success": True,
        "message": "Administrator account updated. Your current session remains active.",
    }


@router.get("/admin/summary")
def admin_summary(request: Request):
    admin = require_admin(request)

    with get_db() as db:
        total_users = db.execute(
            "SELECT COUNT(*) AS count FROM users WHERE role = 'user'"
        ).fetchone()["count"]
        active_users = db.execute(
            "SELECT COUNT(*) AS count FROM users WHERE role = 'user' AND is_active = 1"
        ).fetchone()["count"]
        approved_users = db.execute(
            "SELECT COUNT(*) AS count FROM users WHERE role = 'user' AND is_approved = 1"
        ).fetchone()["count"]
        active_sessions = db.execute(
            """
            SELECT COUNT(*) AS count
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE u.is_active = 1
            """
        ).fetchone()["count"]
        approved_emails = db.execute(
            "SELECT COUNT(*) AS count FROM approved_emails"
        ).fetchone()["count"]

    return {
        "success": True,
        "admin_email": admin["email"],
        "total_users": total_users,
        "active_users": active_users,
        "approved_users": approved_users,
        "active_sessions": active_sessions,
        "approved_emails": approved_emails,
    }


@router.get("/admin/users")
def admin_users(request: Request):
    require_admin(request)

    with get_db() as db:
        rows = db.execute(
            """
            SELECT
                u.*,
                (SELECT COUNT(*) FROM sessions s WHERE s.user_id = u.id) AS session_count,
                (SELECT COUNT(*) FROM audit_logs a
                 WHERE a.user_id = u.id AND a.event = 'LOGIN_SUCCESS') AS login_count
            FROM users u
            ORDER BY
                CASE WHEN u.role = 'admin' THEN 0 ELSE 1 END,
                u.created_at DESC
            """
        ).fetchall()

    return {
        "success": True,
        "users": [
            {
                "id": row["id"],
                "email": row["email"],
                "role": row["role"],
                "is_active": bool(row["is_active"]),
                "is_approved": bool(row["is_approved"]),
                "created_at": row["created_at"],
                "last_login_at": row["last_login_at"],
                "session_count": row["session_count"],
                "login_count": row["login_count"],
            }
            for row in rows
        ],
    }


@router.post("/admin/users/{user_id}/approve")
def approve_user(user_id: int, request: Request):
    admin = require_admin(request)
    require_csrf(request, admin)

    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        if user["role"] == "admin":
            raise HTTPException(status_code=400, detail="The admin is already approved.")

        db.execute(
            "UPDATE users SET is_approved = 1 WHERE id = ?",
            (user_id,),
        )
        db.execute(
            """
            INSERT OR IGNORE INTO approved_emails(email, added_by, created_at)
            VALUES (?, ?, ?)
            """,
            (user["email"], admin["id"], utc_string()),
        )
        audit(db, "USER_APPROVED", admin["id"], f"user={user['email']}", request)

    return {"success": True, "message": "Private access enabled."}


@router.post("/admin/users/{user_id}/disable")
def disable_user(user_id: int, request: Request):
    admin = require_admin(request)
    require_csrf(request, admin)

    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot disable your own admin account.")

    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        db.execute(
            "UPDATE users SET is_active = 0 WHERE id = ?",
            (user_id,),
        )
        db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        audit(db, "USER_DISABLED", admin["id"], f"user={user['email']}", request)

    return {"success": True, "message": "User disabled and logged out."}


@router.post("/admin/users/{user_id}/enable")
def enable_user(user_id: int, request: Request):
    admin = require_admin(request)
    require_csrf(request, admin)

    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        db.execute(
            "UPDATE users SET is_active = 1 WHERE id = ?",
            (user_id,),
        )
        audit(db, "USER_ENABLED", admin["id"], f"user={user['email']}", request)

    return {"success": True, "message": "User enabled."}


@router.delete("/admin/users/{user_id}")
def delete_user(user_id: int, request: Request):
    admin = require_admin(request)
    require_csrf(request, admin)

    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own admin account.")

    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        email = user["email"]
        audit(db, "USER_DELETED", admin["id"], f"user={email}", request)
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))

    return {"success": True, "message": "User permanently deleted."}


@router.get("/admin/approved-emails")
def list_approved_emails(request: Request):
    require_admin(request)

    with get_db() as db:
        rows = db.execute(
            """
            SELECT ae.id, ae.email, ae.created_at, u.email AS added_by_email
            FROM approved_emails ae
            JOIN users u ON u.id = ae.added_by
            ORDER BY ae.created_at DESC
            """
        ).fetchall()

    return {
        "success": True,
        "emails": [
            {
                "id": row["id"],
                "email": row["email"],
                "created_at": row["created_at"],
                "added_by": row["added_by_email"],
            }
            for row in rows
        ],
    }


@router.post("/admin/approved-emails")
def add_approved_email(payload: EmailRequest, request: Request):
    admin = require_admin(request)
    require_csrf(request, admin)

    email = normalize_email(payload.email)
    error = validate_email(email)
    if error:
        raise HTTPException(status_code=422, detail=error)

    if email == ADMIN_EMAIL:
        raise HTTPException(status_code=400, detail="The administrator is always approved.")

    with get_db() as db:
        db.execute(
            """
            INSERT OR IGNORE INTO approved_emails(email, added_by, created_at)
            VALUES (?, ?, ?)
            """,
            (email, admin["id"], utc_string()),
        )

        # If the person already has an account, approve it immediately.
        db.execute(
            "UPDATE users SET is_approved = 1 WHERE email = ?",
            (email,),
        )

        audit(db, "PRIVATE_EMAIL_ADDED", admin["id"], f"email={email}", request)

    return {
        "success": True,
        "message": f"{email} now has private access (or will receive it when they register).",
    }


@router.delete("/admin/approved-emails/{email_id}")
def remove_approved_email(email_id: int, request: Request):
    admin = require_admin(request)
    require_csrf(request, admin)

    with get_db() as db:
        row = db.execute(
            "SELECT * FROM approved_emails WHERE id = ?",
            (email_id,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Approved email not found.")

        email = row["email"]
        db.execute("DELETE FROM approved_emails WHERE id = ?", (email_id,))

        # Removing private approval also removes it from the user's account.
        db.execute(
            """
            UPDATE users
            SET is_approved = 0
            WHERE email = ? AND role != 'admin'
            """,
            (email,),
        )

        audit(db, "PRIVATE_EMAIL_REMOVED", admin["id"], f"email={email}", request)

    return {"success": True, "message": "Private access removed."}


@router.get("/admin/audit")
def admin_audit(request: Request):
    require_admin(request)

    with get_db() as db:
        rows = db.execute(
            """
            SELECT
                a.id,
                a.event,
                a.details,
                a.ip_address,
                a.user_agent,
                a.created_at,
                u.email AS user_email
            FROM audit_logs a
            LEFT JOIN users u ON u.id = a.user_id
            ORDER BY a.id DESC
            LIMIT 500
            """
        ).fetchall()

    return {
        "success": True,
        "events": [
            {
                "id": row["id"],
                "event": row["event"],
                "details": row["details"],
                "ip_address": row["ip_address"],
                "user_agent": row["user_agent"],
                "created_at": row["created_at"],
                "user_email": row["user_email"],
            }
            for row in rows
        ],
    }


# Make sure the database exists when this module is imported.
init_db()

# supabase_auth.py
"""
Supabase Authentication module
Handles user authentication via Supabase Auth
"""
import os
from typing import Optional

from dotenv import load_dotenv

# Load .env before reading config (this module is imported before the app calls load_dotenv)
load_dotenv()
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Initialize Supabase clients
# Public client for user-facing operations
supabase: Optional[Client] = None
# Admin client for server-side operations (bypasses RLS)
supabase_admin: Optional[Client] = None

# Server-side clients must never hold a user session: they are shared by every
# request, so a stored session would leak between users (and be auto-refreshed
# in the background, rotating that user's refresh token).
def _stateless_options() -> ClientOptions:
    return ClientOptions(auto_refresh_token=False, persist_session=False)


def _auth_client() -> Client:
    """Fresh anon client for calls that create a session (sign in/up, refresh)."""
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY, options=_stateless_options())


if SUPABASE_URL and SUPABASE_ANON_KEY:
    # Shared client: only used for stateless calls such as get_user(jwt)
    supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY, options=_stateless_options())
    print("[Auth] Supabase client initialized")
else:
    print("[Auth] Warning: Supabase credentials not found")

if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY, options=_stateless_options())
    print("[Auth] Supabase admin client initialized")


def is_configured() -> bool:
    """Check if Supabase is properly configured"""
    return supabase is not None and supabase_admin is not None


# ===== User Authentication =====

def sign_up(
    email: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    company: str = "",
) -> dict:
    """
    Sign up a new user with email and password
    Returns: {"user": {...}, "session": {...}} or {"error": "..."}
    """
    if not supabase:
        return {"error": "Supabase not configured"}

    try:
        payload: dict = {"email": email, "password": password}
        user_meta = {k: v for k, v in {
            "first_name": first_name,
            "last_name": last_name,
            "company": company,
        }.items() if v}
        if user_meta:
            payload["options"] = {"data": user_meta}

        response = _auth_client().auth.sign_up(payload)

        if response.user:
            return {
                "user": {
                    "id": response.user.id,
                    "email": response.user.email,
                    "created_at": str(response.user.created_at)
                },
                "session": {
                    "access_token": response.session.access_token if response.session else None,
                    "refresh_token": response.session.refresh_token if response.session else None
                } if response.session else None
            }
        else:
            return {"error": "Sign up failed"}
    except Exception as e:
        return {"error": str(e)}


def sign_in(email: str, password: str) -> dict:
    """
    Sign in a user with email and password
    Returns: {"user": {...}, "session": {...}} or {"error": "..."}
    """
    if not supabase:
        return {"error": "Supabase not configured"}

    try:
        response = _auth_client().auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if response.user and response.session:
            return {
                "user": {
                    "id": response.user.id,
                    "email": response.user.email,
                    "role": response.user.role,
                    "created_at": str(response.user.created_at)
                },
                "session": {
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_at": response.session.expires_at
                }
            }
        else:
            return {"error": "Invalid credentials"}
    except Exception as e:
        error_msg = str(e)
        if "Invalid login credentials" in error_msg:
            return {"error": "Invalid email or password"}
        return {"error": error_msg}


def sign_out(access_token: Optional[str], refresh_token: Optional[str] = None) -> dict:
    """
    Revoke the caller's own session (this device only).
    If the access token has expired, a still-valid refresh token is exchanged
    for a fresh access token first so the session can still be revoked.
    Returns: {"success": True} or {"error": "..."}
    """
    if not supabase_admin:
        return {"error": "Supabase not configured"}

    try:
        if access_token and get_user_from_token(access_token) is None:
            access_token = None
        if not access_token and refresh_token:
            refreshed = refresh_session(refresh_token)
            access_token = (refreshed.get("session") or {}).get("access_token")
        if not access_token:
            return {"success": True}  # nothing left to revoke

        supabase_admin.auth.admin.sign_out(access_token, "local")
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


def get_user_from_token(access_token: str) -> Optional[dict]:
    """
    Validate an access token and return user info
    Returns: {"id": ..., "email": ..., "role": ...} or None
    """
    if not supabase:
        return None

    try:
        response = supabase.auth.get_user(access_token)

        if response and response.user:
            app_metadata = response.user.app_metadata or {}

            # Reject disabled accounts — checked against admin-controlled app_metadata
            if app_metadata.get("disabled"):
                return None

            user_meta = response.user.user_metadata or {}
            return {
                "id": response.user.id,
                "email": response.user.email,
                "role": app_metadata.get("role", "user"),
                "created_at": str(response.user.created_at),
                "first_name": user_meta.get("first_name", ""),
                "last_name": user_meta.get("last_name", ""),
                "company": user_meta.get("company", ""),
            }
        return None
    except Exception as e:
        print(f"[Auth] Token validation error: {e}")
        return None


def update_user_profile(user_id: str, first_name: str = "", last_name: str = "", company: str = "") -> dict:
    """
    Update user_metadata (name/company) for an existing user via the admin client.
    Returns: {"success": True} or {"error": "..."}
    """
    if not supabase_admin:
        return {"error": "Supabase admin not configured"}

    try:
        user_meta = {
            "first_name": first_name,
            "last_name": last_name,
            "company": company,
        }
        supabase_admin.auth.admin.update_user_by_id(user_id, {"user_metadata": user_meta})
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


def refresh_session(refresh_token: str) -> dict:
    """
    Refresh an expired session
    Returns: {"session": {...}} or {"error": "..."}
    """
    if not supabase:
        return {"error": "Supabase not configured"}

    try:
        response = _auth_client().auth.refresh_session(refresh_token)

        if response.session:
            return {
                "session": {
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_at": response.session.expires_at
                }
            }
        return {"error": "Failed to refresh session"}
    except Exception as e:
        return {"error": str(e)}


# ===== Password Reset =====

def resend_verification(email: str) -> dict:
    """
    Resend email verification to a user
    Returns: {"success": True} or {"error": "..."}
    """
    if not supabase:
        return {"error": "Supabase not configured"}

    try:
        _auth_client().auth.resend({
            "type": "signup",
            "email": email
        })
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


def request_password_reset(email: str, redirect_url: str) -> dict:
    """
    Send a password reset email
    Returns: {"success": True} or {"error": "..."}
    """
    if not supabase:
        print("[Auth] Password reset failed: Supabase not configured")
        return {"error": "Supabase not configured"}

    try:
        print(f"[Auth] Requesting password reset for {email}, redirect to {redirect_url}")
        _auth_client().auth.reset_password_email(
            email,
            options={"redirect_to": redirect_url}
        )
        print(f"[Auth] Password reset email sent successfully to {email}")
        return {"success": True}
    except Exception as e:
        print(f"[Auth] Password reset error: {e}")
        return {"error": str(e)}


def update_password(access_token: str, new_password: str) -> dict:
    """
    Update user's password (requires valid session from recovery flow)
    Returns: {"success": True} or {"error": "..."}
    """
    if not supabase:
        return {"error": "Supabase not configured"}

    try:
        # Set the session with the recovery access token
        # The recovery token from email link is a valid session
        user = supabase.auth.get_user(access_token)

        if not user or not user.user:
            return {"error": "Invalid or expired session"}

        if not supabase_admin:
            return {"error": "Supabase admin not configured"}

        response = supabase_admin.auth.admin.update_user_by_id(
            user.user.id,
            {"password": new_password}
        )
        if response.user:
            return {"success": True}
        return {"error": "Failed to update password"}
    except Exception as e:
        print(f"[Auth] Password update error: {e}")
        return {"error": str(e)}


# ===== Admin Operations (Server-side only) =====

ADMIN_PAGE_SIZE = 1000


def _iter_all_users():
    """Yield every Supabase user; list_users() alone only returns the first page (50)."""
    page = 1
    while True:
        batch = supabase_admin.auth.admin.list_users(page=page, per_page=ADMIN_PAGE_SIZE)
        yield from batch
        if len(batch) < ADMIN_PAGE_SIZE:
            return
        page += 1


def find_user_by_email(email: str):
    """Return the Supabase user with this email (case-insensitive), or None."""
    target = (email or "").strip().lower()
    return next((u for u in _iter_all_users() if (u.email or "").lower() == target), None)


def admin_create_user(email: str, password: str, role: str = "user") -> dict:
    """
    Create a user directly (admin operation)
    Returns: {"user": {...}} or {"error": "..."}
    """
    if not supabase_admin:
        return {"error": "Supabase admin not configured"}

    try:
        response = supabase_admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,  # Auto-confirm email
            "app_metadata": {"role": role}
        })

        if response.user:
            return {
                "user": {
                    "id": response.user.id,
                    "email": response.user.email,
                    "role": role
                }
            }
        return {"error": "Failed to create user"}
    except Exception as e:
        return {"error": str(e)}


def admin_invite_user(email: str, role: str = "user", redirect_url: str = None) -> dict:
    """
    Send an invite email to a user
    Returns: {"success": True} or {"error": "..."}
    """
    if not supabase_admin:
        return {"error": "Supabase admin not configured"}

    try:
        options = {
            "data": {}
        }
        if redirect_url:
            options["redirect_to"] = redirect_url

        response = supabase_admin.auth.admin.invite_user_by_email(
            email,
            options=options
        )

        if response.user:
            # Write role into app_metadata (admin-controlled) — never user_metadata
            supabase_admin.auth.admin.update_user_by_id(
                response.user.id,
                {"app_metadata": {"role": role}}
            )
            return {"success": True, "user_id": response.user.id}
        return {"error": "Failed to send invite"}
    except Exception as e:
        return {"error": str(e)}


def admin_delete_user(user_id: str) -> dict:
    """
    Delete a user (admin operation)
    Returns: {"success": True} or {"error": "..."}
    """
    if not supabase_admin:
        return {"error": "Supabase admin not configured"}

    try:
        supabase_admin.auth.admin.delete_user(user_id)
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


def admin_list_users() -> dict:
    """
    List all users (admin operation)
    Returns: {"users": [...]} or {"error": "..."}
    """
    if not supabase_admin:
        return {"error": "Supabase admin not configured"}

    try:
        users = []
        for user in _iter_all_users():
            app_metadata = user.app_metadata or {}
            users.append({
                "id": user.id,
                "email": user.email,
                "role": app_metadata.get("role", "user"),
                "status": "disabled" if app_metadata.get("disabled") else "active",
                "created_at": str(user.created_at),
                "last_sign_in": str(user.last_sign_in_at) if user.last_sign_in_at else None,
                "confirmed": user.email_confirmed_at is not None
            })

        return {"users": users}
    except Exception as e:
        return {"error": str(e)}


def admin_set_user_status(email: str, status: str) -> dict:
    """
    Enable or disable a user account in Supabase.
    Writes disabled flag to app_metadata so get_user_from_token enforces it
    on every authenticated request without a separate DB lookup.
    Returns: {"success": True} or {"error": "..."}
    """
    if not supabase_admin:
        return {"error": "Supabase admin not configured"}

    if status not in ("active", "disabled"):
        return {"error": "Status must be 'active' or 'disabled'"}

    try:
        target = find_user_by_email(email)
        if not target:
            return {"error": "User not found", "not_found": True}

        disabled = status == "disabled"
        # Preserve existing app_metadata fields while updating disabled flag
        existing = target.app_metadata or {}
        updated_metadata = {**existing, "disabled": disabled}

        supabase_admin.auth.admin.update_user_by_id(
            target.id,
            {"app_metadata": updated_metadata}
        )
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


def admin_update_user_role(user_id: str, role: str) -> dict:
    """
    Update a user's role (admin operation)
    Returns: {"success": True} or {"error": "..."}
    """
    if not supabase_admin:
        return {"error": "Supabase admin not configured"}

    try:
        response = supabase_admin.auth.admin.update_user_by_id(
            user_id,
            {"app_metadata": {"role": role}}
        )

        if response.user:
            return {"success": True}
        return {"error": "Failed to update user"}
    except Exception as e:
        return {"error": str(e)}


# ===== Usage Tracking =====
# Usage logs live in the Supabase `usage_logs` table (see usage_store.py)

"""Password hashing/verification and login-session validation.

Passwords are hashed with bcrypt. Legacy SHA-256 hashes are still *verified* so the
login flow (see ``auth.ui.authentication_ui``) can transparently re-hash them with
bcrypt on the next successful login, avoiding a mass password reset.
"""

import hashlib
import hmac
from datetime import datetime, timezone

import bcrypt
import streamlit as st

import config


def hash_password(password: str) -> str:
    """Hashes a password using bcrypt. Returns a str suitable for DB storage."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _is_bcrypt_hash(stored_hash) -> bool:
    """True if the stored hash is a bcrypt hash (rather than a legacy SHA-256 hex digest)."""
    return isinstance(stored_hash, str) and stored_hash.startswith(("$2a$", "$2b$", "$2y$"))


def _legacy_sha256_matches(stored_hash: str, provided_password: str) -> bool:
    """Constant-time check against the deprecated SHA-256 scheme (migration only)."""
    legacy = hashlib.sha256(provided_password.encode()).hexdigest()
    return hmac.compare_digest(str(stored_hash), legacy)


def verify_password(stored_password_hash, provided_password) -> bool:
    """Verifies a password against a bcrypt hash, falling back to legacy SHA-256.

    Legacy SHA-256 hashes are accepted only so the login flow can transparently
    re-hash them with bcrypt on the next successful login (see authentication_ui).
    """
    if not stored_password_hash:
        return False
    if _is_bcrypt_hash(stored_password_hash):
        try:
            return bcrypt.checkpw(
                provided_password.encode("utf-8"), stored_password_hash.encode("utf-8")
            )
        except ValueError:
            return False
    return _legacy_sha256_matches(stored_password_hash, provided_password)


def _parse_timestamp(value):
    """Parse an ISO-8601 timestamp (with or without tz) into an aware UTC datetime, or None."""
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def validate_session():
    """Checks that the current session token matches the DB and has not expired."""
    if not st.session_state.get('logged_in'):
        return False  # Not logged in, no session to validate

    try:
        email = st.session_state['username']
        local_token = st.session_state.get('session_token')

        conn = config.get_conn()
        # Fetch the current token + expiry from the database
        result = conn.client.table("users").select("active_session_token, session_expires_at").eq("email", email).single().execute()

        db_token = result.data.get('active_session_token')

        # If tokens don't match, the session is invalid
        if local_token != db_token:
            return False

        # Enforce session expiry. A NULL/absent value means "no expiry recorded"
        # (e.g. a row from before this column existed) and is treated as valid so
        # pre-migration sessions are not force-logged-out; every new login writes
        # a real expiry via authentication_ui.
        expires_at = _parse_timestamp(result.data.get('session_expires_at'))
        if expires_at is not None and datetime.now(timezone.utc) >= expires_at:
            return False

        return True

    except Exception as e:
        # If any error occurs (e.g., user deleted), invalidate the session
        st.error(f"Session validation error: {e}")
        return False

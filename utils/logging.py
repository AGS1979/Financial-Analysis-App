"""Audit-log and user-history writers, backed by Supabase.

These helpers pull the acting user's email from ``st.session_state['username']`` and
fail soft: a logging error is printed to the console but never interrupts the app.
"""

import streamlit as st

import config


def log_user_history(action_type: str, target_id: str, summary: str, details: dict = None):
    """Writes a user-facing history event to the database."""
    try:
        user_email = st.session_state.get('username')
        if not user_email:
            return

        conn = config.get_conn()
        history_entry = {
            "user_email": user_email,
            "action_type": action_type,
            "target_id": target_id,
            "summary": summary,
            "details": details,
        }
        conn.client.table("user_history").insert(history_entry).execute()

    except Exception as e:
        # Log to the console if history logging fails, but don't stop the app
        print(f"WARNING: Failed to write to user_history. Error: {e}")


def get_user_history(limit: int = 10):
    """Fetches the most recent history items for the current user."""
    try:
        user_email = st.session_state.get('username')
        if not user_email:
            return []

        conn = config.get_conn()
        response = conn.client.table("user_history") \
            .select("created_at, action_type, target_id, summary, details") \
            .eq("user_email", user_email) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()

        return response.data if response.data else []

    except Exception as e:
        print(f"WARNING: Failed to fetch user_history. Error: {e}")
        return []


def log_audit_event(action_type: str, status: str, target_id: str = None, details: dict = None):
    """
    Writes a standardized entry to the audit_log table using EMAIL.
    Pulls user_email from the session state.
    """
    try:
        # Get user_email from session state
        user_email = st.session_state.get('username')

        if not user_email:
            # This won't happen for logged-in users, but good to check
            return

        conn = config.get_conn()

        log_entry = {
            "user_email": user_email,
            "action_type": action_type,
            "status": status,
            "target_id": target_id,
            "details": details,
        }

        conn.client.table("audit_log").insert(log_entry).execute()

    except Exception as e:
        # Log to Streamlit console if logging to DB fails
        print(f"CRITICAL: Failed to write to audit_log. Error: {e}")

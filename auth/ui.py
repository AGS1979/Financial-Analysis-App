"""Streamlit UI for authentication: login / sign-up and the admin whitelist panel."""

import re
import uuid
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

import config
from auth.db import (
    add_to_whitelist_db,
    add_user_db,
    get_users_db,
    get_whitelist_db,
    remove_from_whitelist_db,
    update_user_password_db,
)
from auth.session import _is_bcrypt_hash, hash_password, verify_password
from utils.logging import log_audit_event


def authentication_ui():
    """Handles the login and sign-up UI using the Supabase database."""
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        choice = st.selectbox("Login or Sign Up", ["Login", "Sign Up"])

        if choice == "Login":
            st.subheader("Login")
            email = st.text_input("Email Address")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                user_db = get_users_db()  # UPDATED to use database function
                if not user_db.empty and email in user_db["email"].values:
                    user_data = user_db[user_db["email"] == email].iloc[0]
                    stored_hash = user_data["password_hash"]
                    if verify_password(stored_hash, password):

                        # Migrate legacy SHA-256 hashes to bcrypt on successful login,
                        # so no mass password reset is required.
                        if not _is_bcrypt_hash(stored_hash):
                            try:
                                update_user_password_db(email, hash_password(password))
                            except Exception as e:
                                print(f"WARNING: Failed to migrate password hash for {email}: {e}")

                        # --- START: MODIFIED SESSION LOGIC ---
                        # 1. Generate a new unique session token with an expiry.
                        session_token = str(uuid.uuid4())
                        expires_at = datetime.now(timezone.utc) + timedelta(hours=config.SESSION_TTL_HOURS)

                        # 2. Store the new token + expiry in the database.
                        conn = config.get_conn()
                        conn.client.table("users").update({
                            "active_session_token": session_token,
                            "session_expires_at": expires_at.isoformat(),
                        }).eq("email", email).execute()

                        # 3. Store user details in the session state.
                        # We no longer need to query for user_id.
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = email      # This is the email, and our new key for logging
                        st.session_state['session_token'] = session_token
                        st.session_state['session_expires_at'] = expires_at.isoformat()
                        # --- END: MODIFIED SESSION LOGIC ---

                        # --- ADD AUDIT LOG CALL (SUCCESS) ---
                        # This will now work, as log_audit_event pulls 'username' (the email)
                        log_audit_event(action_type="USER_LOGIN", status="SUCCESS")
                        # ---

                        st.rerun()
                    else:
                        st.error("Incorrect password.")
                        # --- ADD AUDIT LOG CALL (FAILURE) ---
                        log_audit_event(action_type="USER_LOGIN_FAILURE", status="FAILURE", details={"email_attempt": email})
                        # ---
                else:
                    st.error("Email address not found.")
                    # --- ADD AUDIT LOG CALL (NOT FOUND) ---
                    log_audit_event(action_type="USER_LOGIN_NOT_FOUND", status="FAILURE", details={"email_attempt": email})
                    # ---

        elif choice == "Sign Up":
            st.subheader("Create New Account")
            new_email = st.text_input("Enter your Email Address")
            new_password = st.text_input("Choose a Password", type="password")

            if st.button("Sign Up"):
                whitelist = get_whitelist_db()  # UPDATED
                is_valid_format = re.match(r"[^@]+@[^@]+\.[^@]+", new_email)
                user_db = get_users_db()  # UPDATED

                if not new_email or not new_password:
                    st.error("Email and password cannot be empty.")
                elif not is_valid_format:
                    st.error("Please enter a valid email address format.")
                elif new_email not in whitelist:
                    st.error("This email address is not authorized for registration. Please contact the administrator.")
                elif not user_db.empty and new_email in user_db["email"].values:
                    st.error("This email is already registered. Please go to the Login tab.")
                else:
                    # UPDATED: Replaced pandas logic with a single call to the database function
                    add_user_db(new_email, hash_password(new_password))
                    st.success("Account created successfully! You can now log in.")
                    st.info("Please switch to the Login tab to sign in.")

    return st.session_state.get('logged_in', False)


def whitelist_manager_ui():
    """Renders a UI in the sidebar for admins to manage the email whitelist in Supabase."""
    admin_password = config.APP_ADMIN_PASSWORD
    if not admin_password:
        return

    # REMOVED: The st.expander to fix the icon text issue.
    # The content is now always visible.
    st.subheader("👑 Admin Panel")  # Added a subheader for clarity
    entered_pass = st.text_input("Enter Admin Password", type="password", key="admin_pass")

    if entered_pass == admin_password:
        st.info("Access Granted. You can now manage the email whitelist.")

        try:
            current_whitelist = get_whitelist_db()
            st.write("Whitelisted Emails:")
            st.dataframe(pd.DataFrame({"Authorized Emails": current_whitelist}), use_container_width=True)

            # Add Email Form
            with st.form("add_email_form", clear_on_submit=True):
                new_email = st.text_input("Add new email to whitelist")
                if st.form_submit_button("Add Email"):
                    if new_email and re.match(r"[^@]+@[^@]+\.[^@]+", new_email):
                        if new_email not in current_whitelist:
                            add_to_whitelist_db(new_email)
                            st.success(f"Added '{new_email}' to the whitelist.")
                            st.rerun()
                        else:
                            st.warning("Email already exists in the whitelist.")
                    else:
                        st.error("Please enter a valid, non-empty email address.")

            # Remove Email Form
            if current_whitelist:
                with st.form("remove_email_form"):
                    email_to_remove = st.selectbox("Remove email from whitelist", options=[""] + current_whitelist)
                    if st.form_submit_button("Remove Email"):
                        if email_to_remove:
                            remove_from_whitelist_db(email_to_remove)
                            st.success(f"Removed '{email_to_remove}' from the whitelist.")
                            st.rerun()
                        else:
                            st.warning("Please select an email to remove.")

        except Exception as e:
            st.error(f"An error occurred managing the whitelist: {e}")

    elif entered_pass:
        st.error("Incorrect admin password.")

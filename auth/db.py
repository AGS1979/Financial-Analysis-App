"""Supabase data-access functions for the ``users`` and ``whitelist`` tables."""

import pandas as pd

import config


# --- Whitelist ---
def get_whitelist_db():
    """Fetches whitelisted emails from the Supabase database."""
    conn = config.get_conn()
    rows = conn.client.table("whitelist").select("email").execute()
    return [row['email'] for row in rows.data]


def add_to_whitelist_db(email: str):
    """Adds a new email to the whitelist table."""
    conn = config.get_conn()
    conn.client.table("whitelist").insert([{"email": email}]).execute()


def remove_from_whitelist_db(email: str):
    """Removes an email from the whitelist table."""
    conn = config.get_conn()
    conn.client.table("whitelist").delete().eq("email", email).execute()


# --- Users ---
def get_users_db():
    """Fetches user data from the Supabase database."""
    conn = config.get_conn()
    rows = conn.client.table("users").select("email, password_hash").execute()
    # Return an empty DataFrame with correct columns if there's no data
    if not rows.data:
        return pd.DataFrame(columns=['email', 'password_hash'])
    return pd.DataFrame(rows.data)


def add_user_db(email: str, hashed_password: str):
    """Adds a new user to the users table."""
    conn = config.get_conn()
    conn.client.table("users").insert([{"email": email, "password_hash": hashed_password}]).execute()


def update_user_password_db(email: str, new_hash: str):
    """Updates a user's stored password hash (used to migrate legacy hashes to bcrypt)."""
    conn = config.get_conn()
    conn.client.table("users").update({"password_hash": new_hash}).eq("email", email).execute()

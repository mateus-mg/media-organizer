#!/usr/bin/env python3
"""Setup script to create admin user in Navidrome test container.

CRITICAL: Navidrome stores passwords in PLAINTEXT in the SQLite database
for Subsonic API authentication. The password field is compared directly
with the 'p' parameter or used in MD5(password+salt) for token auth.
"""

import requests
import sys
import time

NAVIDROME_URL = "http://localhost:4534"
ADMIN_USER = "admin"
ADMIN_PASS = "test123"


def wait_for_navidrome(timeout=60):
    """Wait for Navidrome to be ready."""
    for i in range(timeout):
        try:
            r = requests.get(f"{NAVIDROME_URL}/app", timeout=2)
            if r.status_code == 200:
                print("Navidrome is ready")
                return True
        except requests.ConnectionError:
            pass
        if i % 5 == 0:
            print(f"Waiting for Navidrome... ({i}/{timeout})")
        time.sleep(1)
    return False


def create_first_user():
    """Create the first admin user directly in SQLite.
    
    Navidrome stores passwords in PLAINTEXT for Subsonic API compatibility.
    The password is compared directly with the 'p' parameter or used in
    MD5(password+salt) calculation for token-based auth.
    """
    import sqlite3
    from pathlib import Path
    
    # The database is mounted from host via docker-compose
    db_path = Path(__file__).parent / "fixtures" / "data" / "navidrome.db"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Insert or update admin user with plaintext password
        cursor.execute("""
            INSERT INTO user (id, user_name, name, email, password, is_admin, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(user_name) DO UPDATE SET 
                password=excluded.password, 
                is_admin=excluded.is_admin,
                updated_at=datetime('now')
        """, ('test-admin-id', ADMIN_USER, 'Test Admin', 'test@example.com', ADMIN_PASS, 1))
        
        conn.commit()
        conn.close()
        print(f"Created admin user: {ADMIN_USER}")
        return True
    except Exception as e:
        print(f"Error creating user: {e}")
        return False


def verify_login():
    """Verify we can login with the created user using Subsonic token auth."""
    import hashlib
    import secrets
    
    salt = secrets.token_hex(6)
    token = hashlib.md5(f"{ADMIN_PASS}{salt}".encode()).hexdigest()
    
    url = f"{NAVIDROME_URL}/rest/ping.view"
    params = {
        "u": ADMIN_USER,
        "t": token,
        "s": salt,
        "v": "1.16.1",
        "c": "test-setup",
        "f": "json",
    }
    
    try:
        r = requests.get(url, params=params, timeout=5)
        data = r.json()
        if data.get("subsonic-response", {}).get("status") == "ok":
            print("Login verified successfully")
            return True
        else:
            print(f"Login failed: {data}")
            return False
    except Exception as e:
        print(f"Error verifying login: {e}")
        return False


if __name__ == "__main__":
    print("Setting up Navidrome test user...")
    
    if not wait_for_navidrome():
        print("Navidrome did not start in time")
        sys.exit(1)
    
    # Wait for first-time setup to be ready
    time.sleep(2)
    
    if not create_first_user():
        print("Failed to create user")
        sys.exit(1)
    
    if not verify_login():
        print("Failed to verify login")
        sys.exit(1)
    
    print("Setup complete!")
    sys.exit(0)

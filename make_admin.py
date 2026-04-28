"""
Skrip untuk membuat atau menaikkan akun menjadi admin di Cofind.

Cara pakai:
  Opsi 1 - Naikkan akun yang sudah ada menjadi admin:
    python make_admin.py --username <username>

  Opsi 2 - Buat akun admin baru:
    python make_admin.py --create --username <username> --password <password>
"""

import argparse
import hashlib
import os
import secrets
import sqlite3
import string

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'cofind.db')


def hash_password(password: str) -> str:
    salt = secrets.token_hex(32)
    pwd_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${pwd_hash}"


def list_users(cursor):
    rows = cursor.execute(
        "SELECT id, username, email, is_admin, is_active FROM users ORDER BY id"
    ).fetchall()
    print(f"\n{'ID':<5} {'Username':<25} {'Email':<35} {'Admin':>6} {'Active':>7}")
    print("-" * 80)
    for r in rows:
        print(f"{r[0]:<5} {r[1]:<25} {r[2]:<35} {r[3]:>6} {r[4]:>7}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Admin account manager untuk Cofind.")
    parser.add_argument("--username", required=True, help="Username akun")
    parser.add_argument("--password", default=None, help="Password (hanya untuk --create)")
    parser.add_argument("--create", action="store_true", help="Buat akun admin baru")
    args = parser.parse_args()

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    if args.create:
        # Buat akun admin baru
        if not args.password:
            print("ERROR: --password wajib diisi saat menggunakan --create")
            conn.close()
            return

        email = f"{args.username}@cofind.app"
        existing = cursor.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (args.username, email)
        ).fetchone()
        if existing:
            print(f"ERROR: Username '{args.username}' atau email '{email}' sudah dipakai.")
            list_users(cursor)
            conn.close()
            return

        pwd_hash = hash_password(args.password)
        cursor.execute(
            "INSERT INTO users (email, username, password_hash, is_admin, is_active) VALUES (?, ?, ?, 1, 1)",
            (email, args.username, pwd_hash)
        )
        user_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO user_profiles (user_id, full_name) VALUES (?, ?)",
            (user_id, args.username)
        )
        conn.commit()
        print(f"\n✅ Akun admin baru berhasil dibuat:")
        print(f"   Username : {args.username}")
        print(f"   Email    : {email}")
        print(f"   Password : {args.password}")
        print(f"   is_admin : 1 (admin)\n")

    else:
        # Naikkan akun yang sudah ada menjadi admin
        row = cursor.execute(
            "SELECT id, username, email, is_admin FROM users WHERE username = ?",
            (args.username,)
        ).fetchone()
        if not row:
            print(f"ERROR: Username '{args.username}' tidak ditemukan di database.")
            list_users(cursor)
            conn.close()
            return

        cursor.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (args.username,))
        conn.commit()
        print(f"\n✅ Akun '{args.username}' berhasil dijadikan admin.\n")

    list_users(cursor)
    conn.close()


if __name__ == "__main__":
    main()

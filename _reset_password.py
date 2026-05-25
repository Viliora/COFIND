"""
Reset password user di database Cofind (Supabase/PostgreSQL atau SQLite lokal).
Jalankan: python _reset_password.py --username NAMA --password PASSWORD_BARU
"""
import hashlib
import secrets
import argparse

from db_backend import get_connection


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


parser = argparse.ArgumentParser(description="Reset password user Cofind.")
parser.add_argument("--username", required=True, help="Username akun yang ingin direset")
parser.add_argument("--password", required=True, help="Password baru (min 6 karakter)")
args = parser.parse_args()

if len(args.password) < 6:
    print("ERROR: Password minimal 6 karakter.")
    exit(1)

conn = get_connection()
cursor = conn.cursor()

row = cursor.execute(
    "SELECT id, username, email FROM users WHERE username = ?", (args.username,)
).fetchone()
if not row:
    print(f"ERROR: Username '{args.username}' tidak ditemukan.")
    list_users(cursor)
    conn.close()
    exit(1)

new_hash = hash_password(args.password)
cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, row[0]))
conn.commit()

print(f"\n[OK] Password berhasil direset:")
print(f"   Username : {row[1]}")
print(f"   Email    : {row[2]}")
print(f"   Password : {args.password}\n")

list_users(cursor)
conn.close()

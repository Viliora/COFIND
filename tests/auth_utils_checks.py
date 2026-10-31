"""Smoke checks untuk hash password Argon2id + migrasi SHA256 legacy."""

from auth_utils import hash_password, password_hash_needs_upgrade, verify_password


def _legacy_sha256_hash(password: str) -> str:
    import hashlib
    import secrets

    salt = secrets.token_hex(32)
    pwd_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${pwd_hash}"


def run_checks():
    plain = 'test-password-123'
    hashed = hash_password(plain)
    assert hashed.startswith('$argon2'), hashed
    assert verify_password(plain, hashed)
    assert not verify_password('wrong', hashed)
    assert not password_hash_needs_upgrade(hashed)

    legacy = _legacy_sha256_hash(plain)
    assert verify_password(plain, legacy)
    assert password_hash_needs_upgrade(legacy)


if __name__ == '__main__':
    run_checks()
    print('auth_utils_checks OK')

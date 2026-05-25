"""Integration: /api/auth/* + modul auth_utils."""


def test_signup_login_verify_user_logout(client):
    r = client.post(
        "/api/auth/signup",
        json={
            "email": "auth_int@test.local",
            "username": "auth_int_user",
            "password": "secret12",
            "full_name": "Auth Int",
        },
    )
    assert r.status_code == 201
    body = r.get_json()
    assert body["status"] == "success"
    token = body["token"]
    assert body["user"]["username"] == "auth_int_user"

    r_login = client.post(
        "/api/auth/login",
        json={"email": "auth_int@test.local", "password": "secret12"},
    )
    assert r_login.status_code == 200

    r_bad = client.post(
        "/api/auth/login",
        json={"email": "auth_int@test.local", "password": "salah"},
    )
    assert r_bad.status_code == 401

    r_verify = client.post("/api/auth/verify", json={"token": token})
    assert r_verify.status_code == 200
    assert r_verify.get_json()["user"]["email"] == "auth_int@test.local"

    r_me = client.get("/api/auth/user", headers={"Authorization": f"Bearer {token}"})
    assert r_me.status_code == 200
    assert r_me.get_json()["user"]["id"] == body["user"]["id"]

    r_out = client.post("/api/auth/logout", json={"token": token})
    assert r_out.status_code == 200

    r_after = client.post("/api/auth/verify", json={"token": token})
    assert r_after.status_code == 401


def test_signup_duplicate_email_returns_400(client):
    payload = {
        "email": "dup@test.local",
        "username": "user_a",
        "password": "secret12",
        "full_name": "A",
    }
    assert client.post("/api/auth/signup", json=payload).status_code == 201
    r2 = client.post(
        "/api/auth/signup",
        json={
            "email": "dup@test.local",
            "username": "user_b",
            "password": "secret12",
            "full_name": "B",
        },
    )
    assert r2.status_code == 400


def test_update_profile_with_token(client):
    r = client.post(
        "/api/auth/signup",
        json={
            "email": "prof@test.local",
            "username": "prof_user",
            "password": "secret12",
            "full_name": "Lama",
        },
    )
    assert r.status_code == 201
    token = r.get_json()["token"]

    r_put = client.put(
        "/api/auth/update-profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Baru E2E", "bio": "Halo"},
    )
    assert r_put.status_code == 200
    u = r_put.get_json()["user"]
    assert u["full_name"] == "Baru E2E"

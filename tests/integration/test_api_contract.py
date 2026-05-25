"""
Kontrak API: status code, Content-Type, body, validasi JSON Schema, auth & admin.
Memakai fixture integration (SQLite default; Postgres jika COFIND_INTEGRATION_BACKEND=postgres).
"""
from __future__ import annotations

import pytest

from .api_test_helpers import assert_api_json
from . import json_schemas as S

pytestmark = pytest.mark.api_contract


def test_contract_home_headers_and_schema(client):
    r = client.get("/")
    data = assert_api_json(r, 200, S.HOME)
    assert "COFIND" in data["message"].upper() or "cofind" in data["message"].lower()


def test_contract_api_test_headers_and_schema(client):
    r = client.get("/api/test")
    assert_api_json(r, 200, S.API_TEST)


def test_contract_health_headers_and_schema(client):
    r = client.get("/health")
    assert r.status_code in (200, 503)
    data = assert_api_json(r, r.status_code, S.HEALTH)
    assert data["llm_backend"]
    assert data["llm_available"] is (r.status_code == 200)


def test_contract_coffeeshops_list_schema(client):
    r = client.get("/api/coffeeshops")
    assert_api_json(r, 200, S.COFFEESHOPS_LIST)


def test_contract_auth_signup_schema(client):
    r = client.post(
        "/api/auth/signup",
        json={
            "email": "contract_signup@test.local",
            "username": "contract_signup_u",
            "password": "secret12",
            "full_name": "Contract",
        },
    )
    assert_api_json(r, 201, S.AUTH_SIGNUP_SUCCESS)


def test_contract_auth_login_success_schema(client):
    client.post(
        "/api/auth/signup",
        json={
            "email": "contract_login@test.local",
            "username": "contract_login_u",
            "password": "secret12",
            "full_name": "L",
        },
    )
    r = client.post(
        "/api/auth/login",
        json={"email": "contract_login@test.local", "password": "secret12"},
    )
    assert_api_json(r, 200, S.AUTH_LOGIN_SUCCESS)


def test_contract_auth_login_failure_schema(client):
    r = client.post(
        "/api/auth/login",
        json={"email": "tidak_ada@test.local", "password": "x"},
    )
    assert_api_json(r, 401, S.ERROR_BODY)


def test_contract_auth_verify_and_me_schema(client):
    r0 = client.post(
        "/api/auth/signup",
        json={
            "email": "contract_verify@test.local",
            "username": "contract_verify_u",
            "password": "secret12",
            "full_name": "V",
        },
    )
    token = assert_api_json(r0, 201, S.AUTH_SIGNUP_SUCCESS)["token"]

    r1 = client.post("/api/auth/verify", json={"token": token})
    assert_api_json(r1, 200, S.AUTH_VERIFY_SUCCESS)

    r2 = client.get("/api/auth/user", headers={"Authorization": f"Bearer {token}"})
    assert_api_json(r2, 200, S.AUTH_USER_ME_SUCCESS)


def test_contract_auth_user_no_token_401_schema(client):
    r = client.get("/api/auth/user")
    assert_api_json(r, 401, S.ERROR_BODY)


def test_contract_auth_user_invalid_token_401_schema(client):
    r = client.get(
        "/api/auth/user",
        headers={"Authorization": "Bearer token_tidak_validxxxxxxxx"},
    )
    assert_api_json(r, 401, S.ERROR_BODY)


def test_contract_auth_update_profile_no_token_401_schema(client):
    r = client.put("/api/auth/update-profile", json={"full_name": "X"})
    assert_api_json(r, 401, S.ERROR_BODY)


def test_contract_auth_logout_schema(client):
    r0 = client.post(
        "/api/auth/signup",
        json={
            "email": "contract_logout@test.local",
            "username": "contract_logout_u",
            "password": "secret12",
            "full_name": "O",
        },
    )
    token = assert_api_json(r0, 201, S.AUTH_SIGNUP_SUCCESS)["token"]
    r1 = client.post("/api/auth/logout", json={"token": token})
    assert_api_json(r1, 200, S.AUTH_LOGOUT_SUCCESS)


def test_contract_auth_update_profile_success_schema(client):
    r0 = client.post(
        "/api/auth/signup",
        json={
            "email": "contract_prof@test.local",
            "username": "contract_prof_u",
            "password": "secret12",
            "full_name": "Awal",
        },
    )
    token = assert_api_json(r0, 201, S.AUTH_SIGNUP_SUCCESS)["token"]
    r1 = client.put(
        "/api/auth/update-profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Baru", "bio": "Bio"},
    )
    assert_api_json(r1, 200, S.AUTH_UPDATE_PROFILE_SUCCESS)


def test_contract_admin_users_no_token_401(client):
    r = client.get("/api/admin/users")
    assert_api_json(r, 401, S.ERROR_BODY)
    assert r.get_json()["message"]


def test_contract_admin_users_non_admin_forbidden_403(client):
    r0 = client.post(
        "/api/auth/signup",
        json={
            "email": "contract_user@test.local",
            "username": "contract_norm_u",
            "password": "secret12",
            "full_name": "User",
        },
    )
    token = assert_api_json(r0, 201, S.AUTH_SIGNUP_SUCCESS)["token"]
    r = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert_api_json(r, 403, S.ERROR_BODY)
    assert "admin" in r.get_json()["message"].lower()

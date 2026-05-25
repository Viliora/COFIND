"""Favorit: API + favorites_utils + SQLite."""


def test_favorites_crud_flow(client, seed_coffee_shop):
    pid = seed_coffee_shop
    r_u = client.post(
        "/api/auth/signup",
        json={
            "email": "fav_flow@test.local",
            "username": "fav_flow_user",
            "password": "secret12",
            "full_name": "Fav Flow",
        },
    )
    assert r_u.status_code == 201
    uid = r_u.get_json()["user"]["id"]

    r_add = client.post(
        "/api/favorites",
        json={"user_id": uid, "place_id": pid},
    )
    assert r_add.status_code == 201
    assert r_add.get_json()["status"] == "success"

    r_dup = client.post(
        "/api/favorites",
        json={"user_id": uid, "place_id": pid},
    )
    assert r_dup.status_code == 400

    r_list = client.get(f"/api/users/{uid}/favorites")
    assert r_list.status_code == 200
    lst = r_list.get_json()
    assert lst["status"] == "success"
    assert len(lst["favorites"]) == 1
    assert lst["favorites"][0]["place_id"] == pid

    r_status = client.get(f"/api/coffeeshops/{pid}/favorite-status?user_id={uid}")
    assert r_status.status_code == 200
    assert r_status.get_json()["is_favorite"] is True

    r_count = client.get(f"/api/coffeeshops/{pid}/favorite-count")
    assert r_count.status_code == 200
    assert r_count.get_json()["count"] == 1

    r_del = client.delete(f"/api/favorites/{pid}", json={"user_id": uid})
    assert r_del.status_code == 200

    r_status2 = client.get(f"/api/coffeeshops/{pid}/favorite-status?user_id={uid}")
    assert r_status2.get_json()["is_favorite"] is False


def test_add_favorite_unknown_shop_returns_400(client):
    r_u = client.post(
        "/api/auth/signup",
        json={
            "email": "fav_unknown@test.local",
            "username": "fav_unknown",
            "password": "secret12",
            "full_name": "X",
        },
    )
    assert r_u.status_code == 201
    uid = r_u.get_json()["user"]["id"]
    r = client.post(
        "/api/favorites",
        json={"user_id": uid, "place_id": "ChIJ_tidak_ada"},
    )
    assert r.status_code == 400

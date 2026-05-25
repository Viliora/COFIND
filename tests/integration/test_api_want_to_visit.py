"""Integration: /api/want-to-visit dan terkait."""


def _new_user(client, key: str):
    r = client.post(
        "/api/auth/signup",
        json={
            "email": f"{key}@wtv.test.local",
            "username": f"wtv_{key}",
            "password": "secret12",
            "full_name": "WTV",
        },
    )
    assert r.status_code == 201
    j = r.get_json()
    return j["user"]["id"]


def test_want_to_visit_crud(client, seed_coffee_shop):
    pid = seed_coffee_shop
    uid = _new_user(client, "a")

    r_add = client.post("/api/want-to-visit", json={"user_id": uid, "place_id": pid})
    assert r_add.status_code == 201

    r_dup = client.post("/api/want-to-visit", json={"user_id": uid, "place_id": pid})
    assert r_dup.status_code == 400

    r_stat = client.get(
        f"/api/coffeeshops/{pid}/want-to-visit-status?user_id={uid}",
    )
    assert r_stat.status_code == 200
    assert r_stat.get_json()["is_want_to_visit"] is True

    r_list = client.get(f"/api/users/{uid}/want-to-visit")
    assert r_list.status_code == 200
    items = r_list.get_json()["want_to_visit"]
    assert len(items) == 1
    assert items[0]["place_id"] == pid

    r_del = client.delete(
        f"/api/want-to-visit/{pid}",
        json={"user_id": uid},
    )
    assert r_del.status_code == 200

    r_stat2 = client.get(
        f"/api/coffeeshops/{pid}/want-to-visit-status?user_id={uid}",
    )
    assert r_stat2.get_json()["is_want_to_visit"] is False


def test_want_to_visit_unknown_shop_400(client):
    uid = _new_user(client, "b")
    r = client.post(
        "/api/want-to-visit",
        json={"user_id": uid, "place_id": "ChIJ_tidak_ada"},
    )
    assert r.status_code == 400

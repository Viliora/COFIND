"""Review: API + review_utils + DB."""


def test_create_and_get_review(client, seed_coffee_shop):
    pid = seed_coffee_shop
    r_u = client.post(
        "/api/auth/signup",
        json={
            "email": "rev_flow@test.local",
            "username": "rev_flow_user",
            "password": "secret12",
            "full_name": "Reviewer",
        },
    )
    assert r_u.status_code == 201
    uid = r_u.get_json()["user"]["id"]

    r_post = client.post(
        "/api/reviews",
        json={
            "user_id": uid,
            "place_id": pid,
            "rating": 5,
            "text": "Enak dan nyaman.",
        },
    )
    assert r_post.status_code == 201
    body = r_post.get_json()
    assert body["status"] == "success"
    rid = body["review"]["id"]

    r_get = client.get(f"/api/reviews/{rid}")
    assert r_get.status_code == 200
    g = r_get.get_json()
    assert g["review"]["rating"] == 5
    assert g["review"]["place_id"] == pid


def test_create_review_validation(client, seed_coffee_shop):
    r_u = client.post(
        "/api/auth/signup",
        json={
            "email": "rev_val@test.local",
            "username": "rev_val_user",
            "password": "secret12",
            "full_name": "R",
        },
    )
    assert r_u.status_code == 201
    uid = r_u.get_json()["user"]["id"]
    r = client.post(
        "/api/reviews",
        json={
            "user_id": uid,
            "place_id": seed_coffee_shop,
            "rating": 0,
        },
    )
    assert r.status_code == 400

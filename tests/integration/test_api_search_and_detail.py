"""Integration: pencarian toko & GET by place_id."""


def test_search_query_too_short_returns_400(client):
    r = client.get("/api/coffeeshops/search?q=a")
    assert r.status_code == 400


def test_search_and_get_by_place_id(client, seed_coffee_shop):
    pid = seed_coffee_shop
    r_search = client.get("/api/coffeeshops/search?q=Kopi")
    assert r_search.status_code == 200
    data = r_search.get_json()
    assert data["status"] == "success"
    assert data["total"] >= 1
    assert any(s.get("place_id") == pid for s in data["data"])

    r_place = client.get(f"/api/coffeeshops/place/{pid}")
    assert r_place.status_code == 200
    assert r_place.get_json()["data"]["place_id"] == pid

    r_404 = client.get("/api/coffeeshops/place/ChIJ_missing_xyz")
    assert r_404.status_code == 404

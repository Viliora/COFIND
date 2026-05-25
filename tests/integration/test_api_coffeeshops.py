"""GET /api/coffeeshops — Flask + query DB + join opening_hours."""


def test_get_coffeeshops_empty(client):
    r = client.get("/api/coffeeshops")
    assert r.status_code == 200
    j = r.get_json()
    assert j.get("status") == "success"
    assert j.get("total") == 0


def test_get_coffeeshops_with_data(client, seed_coffee_shop):
    r = client.get("/api/coffeeshops")
    assert r.status_code == 200
    j = r.get_json()
    assert j.get("status") == "success"
    assert j.get("total") == 1
    row = j["data"][0]
    assert row["place_id"] == seed_coffee_shop
    assert row["name"] == "Kopi Integration"
    assert "opening_hours_display" in row

"""Smoke: endpoint tanpa DB atau tanpa ketergantungan berat."""


def test_home_json(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.get_json()
    assert "message" in body


def test_api_test_ok(client):
    r = client.get("/api/test")
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("status") == "ok"
    assert "llm_backend" in data


def test_health(client):
    r = client.get("/health")
    # 503 jika LLM tidak dikonfigurasi di lingkungan tes
    assert r.status_code in (200, 503)
    assert "llm_backend" in r.get_json()

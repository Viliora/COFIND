"""
Pengujian beban CoFind API dengan Locust.

Prasyarat: backend jalan (mis. python app.py), default http://127.0.0.1:5000

Contoh (headless):
  Load:     locust -f tests/performance/locustfile.py --headless -u 50 -r 10 -t 3m
  Stress:   locust -f tests/performance/locustfile.py --headless -u 200 -r 25 -t 10m
  Spike:    locust -f tests/performance/locustfile.py --headless -u 150 -r 80 -t 2m

Host lain:
  set LOCUST_HOST=https://staging.example.com
  atau: locust ... --host http://127.0.0.1:5055

UI: locust -f tests/performance/locustfile.py lalu buka http://localhost:8089
"""
from __future__ import annotations

import os

from locust import HttpUser, between, task

_DEFAULT_HOST = os.environ.get("LOCUST_HOST", "http://127.0.0.1:5000")


class CofindReadHeavyUser(HttpUser):
    """
    Pola baca-dominan (katalog, health) — aman untuk DB tanpa membanjiri signup.
    Sesuaikan bobot @task jika ingin meniru trafik nyata.
    """

    host = _DEFAULT_HOST
    wait_time = between(0.3, 1.5)

    @task(5)
    def health(self) -> None:
        self.client.get("/health", name="GET /health")

    @task(3)
    def root(self) -> None:
        self.client.get("/", name="GET /")

    @task(4)
    def coffeeshops(self) -> None:
        self.client.get("/api/coffeeshops", name="GET /api/coffeeshops")

    @task(3)
    def search_kopi(self) -> None:
        self.client.get(
            "/api/coffeeshops/search?q=kopi",
            name="GET /api/coffeeshops/search",
        )

    @task(2)
    def api_test(self) -> None:
        self.client.get("/api/test", name="GET /api/test")

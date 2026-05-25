/**
 * k6 — Load testing bertahap (ramp-up, steady, ramp-down).
 *
 * Prasyarat: k6 terpasang (https://k6.io/docs/get-started/installation/)
 * Backend jalan di BASE_URL.
 *
 *   k6 run tests/performance/k6/load.js
 *   k6 run -e BASE_URL=http://127.0.0.1:5055 tests/performance/k6/load.js
 */
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 20 },
    { duration: "2m", target: 20 },
    { duration: "20s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<3000"],
  },
};

const BASE = __ENV.BASE_URL || "http://127.0.0.1:5000";

export default function () {
  let r = http.get(`${BASE}/health`);
  check(r, {
    "health 200 or 503": (res) => res.status === 200 || res.status === 503,
  });

  r = http.get(`${BASE}/api/coffeeshops`);
  check(r, { "coffeeshops 200": (res) => res.status === 200 });

  r = http.get(`${BASE}/api/coffeeshops/search?q=kopi`);
  check(r, { "search 200": (res) => res.status === 200 });

  sleep(1);
}

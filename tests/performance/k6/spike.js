/**
 * k6 — Spike testing: lonjakan user singkat lalu turun.
 *
 *   k6 run tests/performance/k6/spike.js
 *   k6 run -e BASE_URL=http://127.0.0.1:5000 tests/performance/k6/spike.js
 */
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "5s", target: 1 },
    { duration: "15s", target: 150 },
    { duration: "1m", target: 150 },
    { duration: "15s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.15"],
  },
};

const BASE = __ENV.BASE_URL || "http://127.0.0.1:5000";

export default function () {
  const r = http.get(`${BASE}/health`);
  check(r, {
    "health ok": (res) => res.status === 200 || res.status === 503,
  });
  http.get(`${BASE}/api/coffeeshops`);
  sleep(0.3);
}

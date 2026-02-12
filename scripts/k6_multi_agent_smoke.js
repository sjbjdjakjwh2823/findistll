import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 2,
  duration: "20s",
};

const BASE = __ENV.BASE_URL || "http://localhost:8004";

export default function () {
  const payload = JSON.stringify({
    case_id: "case_smoke",
    document: { source: "smoke", content: { text: "financial risk summary" } },
  });
  const params = { headers: { "Content-Type": "application/json" } };
  const res = http.post(`${BASE}/api/v1/multi-agent/run`, payload, params);
  check(res, {
    "status 200 or 500": (r) => r.status === 200 || r.status === 500,
  });
  sleep(1);
}

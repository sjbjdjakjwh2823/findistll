import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 5,
  duration: "30s",
};

const BASE = __ENV.BASE_URL || "http://localhost:8004";

export default function () {
  const payload = JSON.stringify({
    query: "risk analysis for credit default",
    filters: { approval_status: "approved" },
    top_k: 5,
    use_graph_expansion: true,
  });
  const params = { headers: { "Content-Type": "application/json" } };
  const res = http.post(`${BASE}/api/v1/retrieval/search`, payload, params);
  check(res, {
    "status 200": (r) => r.status === 200,
  });
  sleep(1);
}

// Uji beban ringan dengan Grafana k6.
// Jalankan tiga kali:
//   k6 run -e VUS=1  loadtest.js
//   k6 run -e VUS=5  loadtest.js
//   k6 run -e VUS=10 loadtest.js
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:8000';

export const options = {
  vus: Number(__ENV.VUS || 1),
  duration: __ENV.DURATION || '60s',
  thresholds: {
    http_req_failed: ['rate<0.01'],      // error rate < 1%
    http_req_duration: ['p(95)<500'],    // p95 < 500 ms
  },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)'],
};

export default function () {
  const res = http.post(
    `${BASE}/orders`,
    JSON.stringify({ product_id: 'P-LOAD', quantity: 1 }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  check(res, { 'status 201': (r) => r.status === 201 });
  sleep(0.1);
}

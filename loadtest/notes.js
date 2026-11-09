import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const N = parseInt(__ENV.USERS || '40');
const RAMP_UP = __ENV.RAMP_UP || '2m30s';
const STEADY = __ENV.STEADY || '5m';
const RAMP_DOWN = __ENV.RAMP_DOWN || '2m';
const RESULT = __ENV.RESULT || 'run';

export const options = {
  stages: [
    { duration: RAMP_UP, target: N },
    { duration: STEADY, target: N },
    { duration: RAMP_DOWN, target: 0 },
  ],
  summaryTrendStats: ['avg', 'min', 'med', 'p(95)', 'p(99)', 'max'],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1000'],
  },
};

const json = { headers: { 'Content-Type': 'application/json' } };

function read(url, name) {
  const res = http.get(url, { tags: { name } });
  check(res, { [`${name} 200`]: (r) => r.status === 200 });
  return res;
}

export default function () {
  const author = `user-${__VU}`;

  const created = http.post(
    `${BASE_URL}/notes`,
    JSON.stringify({ text: `note from ${author} iter ${__ITER}`, author }),
    Object.assign({ tags: { name: 'POST /notes' } }, json),
  );
  check(created, { 'POST /notes 201': (r) => r.status === 201 });
  const newId = created.status === 201 ? created.json('id') : null;

  const list = read(`${BASE_URL}/notes`, 'GET /notes');
  let ids = [];
  if (list.status === 200) {
    ids = list.json().map((n) => n.id);
  }

  if (newId !== null) {
    read(`${BASE_URL}/notes/${newId}`, 'GET /notes/{id}');
  }
  read(`${BASE_URL}/authors/${author}`, 'GET /authors/{author}');
  read(`${BASE_URL}/notes`, 'GET /notes');

  for (let i = 0; i < 3 && ids.length > 0; i++) {
    const id = ids[Math.floor(Math.random() * ids.length)];
    const res = http.get(`${BASE_URL}/notes/${id}`, { tags: { name: 'GET /notes/{id}' } });
    check(res, { 'GET /notes/{id} 200 or 404': (r) => r.status === 200 || r.status === 404 });
  }

  read(`${BASE_URL}/notes`, 'GET /notes');
  read(`${BASE_URL}/notes`, 'GET /notes');

  sleep(1);
}

export function handleSummary(data) {
  const m = data.metrics;
  const d = m.http_req_duration.values;
  const report = {
    users: N,
    requests: m.http_reqs.values.count,
    rps: Number(m.http_reqs.values.rate.toFixed(1)),
    error_rate: Number((m.http_req_failed.values.rate * 100).toFixed(2)),
    p50_ms: Number(d.med.toFixed(1)),
    p95_ms: Number(d['p(95)'].toFixed(1)),
    p99_ms: Number(d['p(99)'].toFixed(1)),
    max_ms: Number(d.max.toFixed(1)),
  };
  const line = `requests=${report.requests} rps=${report.rps} errors=${report.error_rate}% p50=${report.p50_ms}ms p95=${report.p95_ms}ms p99=${report.p99_ms}ms\n`;
  return {
    stdout: line,
    [`loadtest/results/${RESULT}.json`]: JSON.stringify(report, null, 2),
    [`loadtest/results/${RESULT}-full.json`]: JSON.stringify(data, null, 2),
  };
}

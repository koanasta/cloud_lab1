import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.request

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def request(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE_URL + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.headers, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.headers, json.loads(e.read() or b"null")


def notes_count(author):
    status, _, body = request("GET", f"/authors/{author}")
    return body["notes_count"] if status == 200 else 0


def check(name, condition, details):
    print(("PASS " if condition else "FAIL ") + name + " | " + details)
    return condition


def test_sync():
    author = f"idem-{uuid.uuid4().hex[:8]}"
    key = str(uuid.uuid4())
    body = {"text": "idempotency test", "author": author}
    headers = {"Idempotency-Key": key}

    s1, h1, b1 = request("POST", "/notes", body, headers)
    s2, h2, b2 = request("POST", "/notes", body, headers)
    count = notes_count(author)
    s3, _, b3 = request("POST", "/notes", {"text": "other", "author": author}, headers)

    ok = True
    ok &= check("two identical requests -> same status", s1 == s2 == 201, f"{s1}, {s2}")
    ok &= check("two identical requests -> same body", b1 == b2, f"{b1} vs {b2}")
    ok &= check("second response marked as replay", h2.get("Idempotent-Replayed") == "true", str(h2.get("Idempotent-Replayed")))
    ok &= check("exactly one row in DB", count == 1, f"notes_count={count}")
    ok &= check("same key, different body -> 422", s3 == 422, f"{s3} {b3}")
    return ok


def test_async():
    author = f"idem-async-{uuid.uuid4().hex[:8]}"
    key = str(uuid.uuid4())
    body = {"text": "idempotency async test", "author": author}
    headers = {"Idempotency-Key": key, "Prefer": "respond-async"}

    s1, _, b1 = request("POST", "/notes", body, headers)
    if s1 != 202:
        print(f"SKIP async: queue is not enabled on this server (got {s1})")
        return True
    s2, _, b2 = request("POST", "/notes", body, headers)
    for _ in range(30):
        _, _, job = request("GET", b1["status_url"])
        if job.get("status") == "done":
            break
        time.sleep(1)
    count = notes_count(author)

    ok = True
    ok &= check("async: two identical requests -> same job", b1 == b2 and s2 == 202, f"{b1['job_id']} vs {b2['job_id']}")
    ok &= check("async: job finished", job.get("status") == "done", str(job))
    ok &= check("async: exactly one row in DB", count == 1, f"notes_count={count}")
    return ok


if __name__ == "__main__":
    print(f"BASE_URL={BASE_URL}")
    results = [test_sync(), test_async()]
    sys.exit(0 if all(results) else 1)

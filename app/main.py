import hashlib
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager

import boto3
import redis
from fastapi import FastAPI, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.common import cache, count, make_pool, migrate

log = logging.getLogger("uvicorn.error")

CACHE_ENABLED = os.environ.get("CACHE_ENABLED", "false").lower() == "true"
CACHE_TTL = int(os.environ.get("CACHE_TTL", "30"))
QUEUE_URL = os.environ.get("QUEUE_URL")
IDEMPOTENCY_TTL = 24 * 60 * 60
JOB_TTL = 24 * 60 * 60
LIST_LIMIT = 50
LIST_KEY = "notes:list"

pool = make_pool(int(os.environ.get("DB_POOL_SIZE", "10")))
sqs = boto3.client("sqs", region_name=os.environ.get("AWS_REGION")) if QUEUE_URL else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open(wait=True)
    with pool.connection() as conn:
        migrate(conn)
    log.info("started, cache_enabled=%s ttl=%s queue=%s", CACHE_ENABLED, CACHE_TTL, bool(QUEUE_URL))
    yield
    log.info("SIGTERM received, finishing in-flight requests and closing DB pool")
    pool.close()
    if cache is not None:
        cache.close()


app = FastAPI(title="Notes API", lifespan=lifespan)


class NoteIn(BaseModel):
    text: str
    author: str = "anonymous"


def note_row(r):
    return {"id": r[0], "text": r[1], "author": r[2], "created_at": r[3]}


def read_notes_from_db():
    count("db_queries")
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT id, text, author, created_at FROM notes ORDER BY id DESC LIMIT %s", (LIST_LIMIT,)
        ).fetchall()
    return jsonable_encoder([note_row(r) for r in rows])


def idempotency_start(key, body_hash):
    stored_key = f"idem:{key}"
    pending = json.dumps({"state": "pending", "hash": body_hash})
    if cache.set(stored_key, pending, nx=True, ex=IDEMPOTENCY_TTL):
        return None
    raw = cache.get(stored_key)
    if raw is None:
        return idempotency_start(key, body_hash)
    stored = json.loads(raw)
    if stored["hash"] != body_hash:
        raise HTTPException(422, "Idempotency-Key was already used with a different request body")
    if stored["state"] == "pending":
        raise HTTPException(409, "A request with this Idempotency-Key is still being processed")
    count("idempotent_replays")
    return JSONResponse(stored["body"], status_code=stored["status"], headers={"Idempotent-Replayed": "true"})


def idempotency_finish(key, body_hash, status, body):
    cache.set(
        f"idem:{key}",
        json.dumps({"state": "done", "hash": body_hash, "status": status, "body": body}),
        ex=IDEMPOTENCY_TTL,
    )


def insert_note(note):
    count("db_queries")
    with pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO notes (text, author) VALUES (%s, %s) RETURNING id", (note.text, note.author)
        ).fetchone()
    return 201, {"id": row[0], "text": note.text, "author": note.author}


def enqueue_note(note, job_id):
    cache.set(f"job:{job_id}", json.dumps({"status": "queued"}), ex=JOB_TTL)
    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps({"job_id": job_id, "text": note.text, "author": note.author}),
    )
    count("jobs_enqueued")
    return 202, {"job_id": job_id, "status": "queued", "status_url": f"/jobs/{job_id}"}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/debug/error", include_in_schema=False)
def debug_error():
    raise RuntimeError("test error for CloudWatch alarm")


@app.get("/notes")
def list_notes():
    if not CACHE_ENABLED or cache is None:
        return read_notes_from_db()
    try:
        cached = cache.get(LIST_KEY)
    except redis.RedisError:
        cached = None
    if cached is not None:
        count("cache_hits")
        return json.loads(cached)
    count("cache_misses")
    notes = read_notes_from_db()
    try:
        cache.set(LIST_KEY, json.dumps(notes), ex=CACHE_TTL)
    except redis.RedisError:
        pass
    return notes


@app.get("/notes/{note_id}")
def get_note(note_id: int):
    count("db_queries")
    with pool.connection() as conn:
        r = conn.execute(
            "SELECT id, text, author, created_at FROM notes WHERE id = %s", (note_id,)
        ).fetchone()
    if r is None:
        raise HTTPException(404, "Note not found")
    return note_row(r)


@app.post("/notes", status_code=201, responses={202: {"description": "Accepted for async processing"}})
def create_note(
    note: NoteIn,
    idempotency_key: str | None = Header(None),
    prefer: str | None = Header(None),
):
    use_queue = sqs is not None and cache is not None and prefer is not None and "respond-async" in prefer
    use_idempotency = idempotency_key is not None and cache is not None
    body_hash = hashlib.sha256(
        json.dumps([note.text, note.author, use_queue]).encode()
    ).hexdigest()

    if use_idempotency:
        replay = idempotency_start(idempotency_key, body_hash)
        if replay is not None:
            return replay

    try:
        if use_queue:
            job_id = hashlib.sha256(idempotency_key.encode()).hexdigest()[:32] if use_idempotency else uuid.uuid4().hex
            status, body = enqueue_note(note, job_id)
        else:
            status, body = insert_note(note)
    except Exception:
        if use_idempotency:
            cache.delete(f"idem:{idempotency_key}")
        raise

    if use_idempotency:
        idempotency_finish(idempotency_key, body_hash, status, body)
    headers = {"Location": body["status_url"]} if status == 202 else None
    return JSONResponse(body, status_code=status, headers=headers)


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    if cache is None:
        raise HTTPException(404, "Job not found")
    raw = cache.get(f"job:{job_id}")
    if raw is None:
        raise HTTPException(404, "Job not found")
    return {"job_id": job_id, **json.loads(raw)}


@app.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int):
    count("db_queries")
    with pool.connection() as conn:
        cur = conn.execute("DELETE FROM notes WHERE id = %s", (note_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "Note not found")


@app.get("/authors/{author}")
def get_author(author: str):
    count("db_queries")
    with pool.connection() as conn:
        r = conn.execute(
            "SELECT count(*), max(created_at) FROM notes WHERE author = %s", (author,)
        ).fetchone()
    if r[0] == 0:
        raise HTTPException(404, "Author not found")
    return {"author": author, "notes_count": r[0], "last_note_at": r[1]}


STAT_NAMES = [
    "cache_hits", "cache_misses", "db_queries", "idempotent_replays",
    "jobs_enqueued", "jobs_processed", "jobs_duplicates",
]


@app.get("/stats")
def stats():
    result = {"cache_enabled": CACHE_ENABLED, "cache_ttl": CACHE_TTL, "queue_enabled": sqs is not None}
    if cache is None:
        return result
    values = cache.mget([f"stats:{n}" for n in STAT_NAMES])
    for n, v in zip(STAT_NAMES, values):
        result[n] = int(v or 0)
    lookups = result["cache_hits"] + result["cache_misses"]
    result["hit_ratio"] = round(result["cache_hits"] / lookups, 3) if lookups else None
    return result


@app.post("/stats/reset", include_in_schema=False)
def reset_stats():
    if cache is not None:
        cache.delete(*[f"stats:{n}" for n in STAT_NAMES])
    return {"reset": True}

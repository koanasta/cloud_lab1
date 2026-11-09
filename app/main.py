import json
import logging
import os
from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

log = logging.getLogger("uvicorn.error")

CACHE_ENABLED = os.environ.get("CACHE_ENABLED", "false").lower() == "true"
CACHE_TTL = int(os.environ.get("CACHE_TTL", "30"))
LIST_LIMIT = 50
LIST_KEY = "notes:list"

conninfo = " ".join([
    f"host={os.environ['DB_HOST']}",
    f"port={os.environ.get('DB_PORT', '5432')}",
    f"dbname={os.environ['DB_NAME']}",
    f"user={os.environ['DB_USER']}",
    f"password={os.environ['DB_PASSWORD']}",
])
pool = ConnectionPool(conninfo, min_size=1, max_size=int(os.environ.get("DB_POOL_SIZE", "10")), open=False)

cache = None
if os.environ.get("REDIS_HOST"):
    cache = redis.Redis(
        host=os.environ["REDIS_HOST"],
        port=int(os.environ.get("REDIS_PORT", "6379")),
        socket_timeout=0.5,
        socket_connect_timeout=0.5,
    )


def count(name):
    if cache is None:
        return
    try:
        cache.incr(f"stats:{name}")
    except redis.RedisError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open(wait=True)
    with pool.connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id SERIAL PRIMARY KEY,
                text TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            )""")
        conn.execute("ALTER TABLE notes ADD COLUMN IF NOT EXISTS author TEXT NOT NULL DEFAULT 'anonymous'")
        conn.execute("CREATE INDEX IF NOT EXISTS notes_author_idx ON notes (author)")
    log.info("started, cache_enabled=%s ttl=%s", CACHE_ENABLED, CACHE_TTL)
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


@app.post("/notes", status_code=201)
def create_note(note: NoteIn):
    count("db_queries")
    with pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO notes (text, author) VALUES (%s, %s) RETURNING id", (note.text, note.author)
        ).fetchone()
    return {"id": row[0], "text": note.text, "author": note.author}


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


@app.get("/stats")
def stats():
    result = {"cache_enabled": CACHE_ENABLED, "cache_ttl": CACHE_TTL}
    if cache is None:
        return result
    names = ["cache_hits", "cache_misses", "db_queries"]
    values = cache.mget([f"stats:{n}" for n in names])
    for n, v in zip(names, values):
        result[n] = int(v or 0)
    lookups = result["cache_hits"] + result["cache_misses"]
    result["hit_ratio"] = round(result["cache_hits"] / lookups, 3) if lookups else None
    return result


@app.post("/stats/reset", include_in_schema=False)
def reset_stats():
    if cache is not None:
        cache.delete("stats:cache_hits", "stats:cache_misses", "stats:db_queries")
    return {"reset": True}

import os

import redis
from psycopg_pool import ConnectionPool

conninfo = " ".join([
    f"host={os.environ['DB_HOST']}",
    f"port={os.environ.get('DB_PORT', '5432')}",
    f"dbname={os.environ['DB_NAME']}",
    f"user={os.environ['DB_USER']}",
    f"password={os.environ['DB_PASSWORD']}",
])


def make_pool(max_size):
    return ConnectionPool(conninfo, min_size=1, max_size=max_size, open=False)


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


def migrate(conn):
    conn.execute("SELECT pg_advisory_xact_lock(4242)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY,
            text TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )""")
    conn.execute("ALTER TABLE notes ADD COLUMN IF NOT EXISTS author TEXT NOT NULL DEFAULT 'anonymous'")
    conn.execute("ALTER TABLE notes ADD COLUMN IF NOT EXISTS request_id TEXT UNIQUE")
    conn.execute("CREATE INDEX IF NOT EXISTS notes_author_idx ON notes (author)")

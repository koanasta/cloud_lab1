import json
import logging
import os
import signal
import time

import boto3

from app.common import cache, count, make_pool, migrate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")

QUEUE_URL = os.environ["QUEUE_URL"]
DELAY = int(os.environ.get("WORKER_DELAY_MS", "0")) / 1000
JOB_TTL = 24 * 60 * 60

sqs = boto3.client("sqs", region_name=os.environ.get("AWS_REGION"))
pool = make_pool(2)
running = True


def stop(signum, frame):
    global running
    log.info("SIGTERM received, finishing current batch")
    running = False


def set_job(job_id, data):
    if cache is not None:
        cache.set(f"job:{job_id}", json.dumps(data), ex=JOB_TTL)


def process(message):
    body = json.loads(message["Body"])
    job_id = body["job_id"]
    receive_count = int(message["Attributes"].get("ApproximateReceiveCount", "1"))
    set_job(job_id, {"status": "processing", "attempt": receive_count})
    if DELAY:
        time.sleep(DELAY)
    count("db_queries")
    with pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO notes (text, author, request_id) VALUES (%s, %s, %s) "
            "ON CONFLICT (request_id) DO NOTHING RETURNING id",
            (body["text"], body["author"], job_id),
        ).fetchone()
        if row is None:
            row = conn.execute("SELECT id FROM notes WHERE request_id = %s", (job_id,)).fetchone()
            count("jobs_duplicates")
            log.info("job %s already processed, note %s, attempt %s", job_id, row[0], receive_count)
    set_job(job_id, {"status": "done", "note_id": row[0], "attempt": receive_count})
    count("jobs_processed")


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    pool.open(wait=True)
    with pool.connection() as conn:
        migrate(conn)
    log.info("worker started, delay=%ss", DELAY)
    while running:
        resp = sqs.receive_message(
            QueueUrl=QUEUE_URL,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=10,
            AttributeNames=["ApproximateReceiveCount"],
        )
        for message in resp.get("Messages", []):
            try:
                process(message)
            except Exception:
                log.exception("job failed, message will be redelivered after visibility timeout")
                continue
            sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=message["ReceiptHandle"])
    pool.close()
    log.info("worker stopped")


if __name__ == "__main__":
    main()

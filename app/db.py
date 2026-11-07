import json
from contextlib import contextmanager
from collections.abc import Iterator
from typing import Any
import psycopg
from psycopg.rows import dict_row
from app.config import settings

@contextmanager
def connection() -> Iterator[Any]:
    # Render provides a PostgreSQL connection URL. Prefer its external URL
    # for a FastAPI process running on your computer.
    url = settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is missing from .env")
    with psycopg.connect(url, connect_timeout=10) as conn:
        typed_conn: Any = conn
        typed_conn.row_factory = dict_row
        yield typed_conn

def audit(conn, actor, tenant, action, detail):
    conn.execute('INSERT INTO audit_events (actor,tenant_id,action,detail) VALUES (%s,%s,%s,%s)',
                 (actor, tenant, action, json.dumps(detail)))
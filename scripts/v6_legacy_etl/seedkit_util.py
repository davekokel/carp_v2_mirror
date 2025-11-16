#!/usr/bin/env python3
import os, sys, psycopg
from contextlib import contextmanager

CONN = os.environ.get("CONN")
if not CONN:
    print("ERROR: Set CONN env var (e.g. postgres://…)", file=sys.stderr)
    sys.exit(1)

@contextmanager
def get_conn():
    with psycopg.connect(CONN) as conn:
        yield conn
        conn.commit()

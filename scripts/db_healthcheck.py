#!/usr/bin/env python3
from __future__ import annotations
import os, sys, time
from pathlib import Path
from urllib.parse import urlparse
import psycopg2

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT/".env.staging.direct"

def load_env(fn: Path):
    if not fn.exists():
        print(f"ERR: missing {fn}", file=sys.stderr)
        sys.exit(2)
    for line in fn.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith("#"): continue
        if "=" not in line: continue
        k,v = line.split("=",1)
        v = v.strip().strip('"').strip("'")
        os.environ[k.strip()] = v

def main():
    load_env(ENV)
    url = os.environ.get("DB_URL","").strip()
    if not url:
        print("ERR: DB_URL not set", file=sys.stderr)
        sys.exit(2)

    p = urlparse(url)
    host = p.hostname or os.environ.get("PGHOST","")
    port = p.port or int(os.environ.get("PGPORT","5432"))
    db   = (p.path or "/postgres").lstrip("/") or os.environ.get("PGDATABASE","postgres")
    user = p.username or os.environ.get("PGUSER","postgres")
    sslmode = "require"
    t0 = time.perf_counter()
    try:
        conn = psycopg2.connect(url, connect_timeout=5, sslmode=sslmode)
    except Exception as e:
        print(f"ERR: connect failed: {e}", file=sys.stderr)
        sys.exit(1)
    dt = (time.perf_counter()-t0)*1000.0
    cur = conn.cursor()
    cur.execute("select inet_server_addr()::text, inet_server_port(), current_setting('server_version')")
    addr, sport, ver = cur.fetchone()
    cur.execute("select count(*) from public.fish")
    fish_n = cur.fetchone()[0]
    conn.close()

    print(f"OK: host={host}:{port} db={db} user={user} → addr={addr}:{sport} ver={ver} latency≈{dt:.1f} ms fish={fish_n}")
    sys.exit(0)

if __name__ == "__main__":
    main()
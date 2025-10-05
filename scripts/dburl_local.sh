#!/usr/bin/env bash
set -euo pipefail
if getent hosts host.docker.internal >/dev/null 2>&1; then
  echo "postgresql://postgres@host.docker.internal:5432/postgres?sslmode=disable"
else
  echo "postgresql://postgres@127.0.0.1:5432/postgres?sslmode=disable"
fi

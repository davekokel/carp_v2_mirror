#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# build file list (exclude archives and .bak)
mapfile -t FILES < <(
  git ls-files \
    'supabase/migrations/**/*.sql' \
    ':!:supabase/migrations/_archive/**' \
    ':!:supabase/migrations/_archive_*/**' \
    ':!:supabase/migrations/_archive_all/**' \
    ':!:supabase/migrations/_archive_legacy/**' \
    ':!:supabase/migrations/**/**.bak.sql' \
  2>/dev/null
)

if [ ${#FILES[@]} -eq 0 ]; then
  echo "No migration SQL files found (non-archived)."
  exit 0
fi

echo "Formatting ${#FILES[@]} migration file(s)..."

# pg_format pass (if available)
if command -v pg_format >/dev/null 2>&1; then
  for f in "${FILES[@]}"; do
    pg_format -i --keyword-case 1 --spaces 4 --wrap-limit 120 "$f"
  done
else
  echo "pg_format not found; skipping formatter pass"
fi

# regex normalizations sqlfluff won't fix

# explicit table aliasing: FROM/JOIN t a -> FROM/JOIN t AS a
for f in "${FILES[@]}"; do
  perl -0777 -pe 's/\b(from|join)\s+([A-Za-z0-9_."-]+)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b(?!\s*AS)/$1 $2 AS $3/gi' -i "$f"
done

# drop column self-alias: "x AS x" -> "x"
for f in "${FILES[@]}"; do
  perl -0777 -pe 's/\b([A-Za-z_][A-Za-z0-9_\.]*)\s+AS\s+\1\b/$1/gi' -i "$f"
done

# ensure a space after commas before quoted literals: ", '"
for f in "${FILES[@]}"; do
  perl -0777 -pe "s/,\s*'/, '/g" -i "$f"
done

# sqlfluff fix + lint
sqlfluff fix  supabase/migrations --dialect postgres || true
sqlfluff lint supabase/migrations --dialect postgres

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
BASELINE="$ROOT/supabase/migrations/00000000000001_baseline.sql"
PRELUDE="$ROOT/supabase/migrations/00000000000000_prelude.sql"

[ -s "$BASELINE" ] || { echo "❌ Baseline not found or empty: $BASELINE"; exit 1; }
[ -s "$PRELUDE" ]  || { echo "❌ Prelude not found or empty:  $PRELUDE";  exit 1; }

# All sequences referenced via nextval('public.xyz')
mapfile -t REFS < <(grep -oE "nextval\('public\.([a-zA-Z0-9_]+)'" "$BASELINE" \
  | sed -E "s/^nextval\('public\.//; s/'$//" | sort -u)

if (( ${#REFS[@]} == 0 )); then
  echo "✅ Baseline references no sequences via nextval()."
  exit 0
fi

missing=()
echo "• Sequences referenced in baseline:"
for s in "${REFS[@]}"; do
  echo "  - public.$s"
  if ! grep -qiE "CREATE\s+SEQUENCE\s+IF\s+NOT\s+EXISTS\s+public\.${s}\b" "$PRELUDE"; then
    missing+=("$s")
  fi
done

if (( ${#missing[@]} )); then
  echo ""
  echo "❌ Missing in prelude:"
  for s in "${missing[@]}"; do
    echo "  - public.$s"
  done
  echo ""
  echo "👉 Add these lines to $PRELUDE:"
  for s in "${missing[@]}"; do
    echo "CREATE SEQUENCE IF NOT EXISTS public.${s};"
  done

  # Optional: if a local DB is running and psql env vars are set, show if they exist
  if command -v psql >/dev/null 2>&1; then
    echo ""
    echo "🔎 Local DB check (if PG* env vars are set):"
    for s in "${missing[@]}"; do
      res="$(psql -Atqc "select to_regclass('public.${s}') is not null;" 2>/dev/null || true)"
      case "$res" in
        t) echo "  public.${s}: present in DB";;
        f|"") echo "  public.${s}: NOT present";;
      esac
    done
  fi

  exit 2
fi

echo "✅ All referenced sequences are declared in the prelude."

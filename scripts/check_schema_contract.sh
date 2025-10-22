#!/usr/bin/env bash
set -euo pipefail

: "${DB_URL:?set DB_URL (e.g. export DB_URL=postgresql://...)}"

root="$(git rev-parse --show-toplevel)"
file="$root/supabase/schema_contract.txt"

miss=0
soft_mode=0

# normalize a comma-separated type list
norm_types() {
  echo "$1" \
    | tr 'A-Z' 'a-z' \
    | sed -E 's/[[:space:]]+//g; s/\bint\b/integer/g; s/\bint4\b/integer/g; s/\bbool\b/boolean/g'
}

while IFS= read -r raw; do
  line="${raw%%#*}"; line="$(echo "$line" | xargs)"

  [[ "$raw" =~ SOFT ]] && soft_mode=1
  [[ -z "$line" ]] && continue

  report_missing() {
    local what="$1"
    if [[ $soft_mode -eq 1 ]]; then
      echo "⚠️  soft-missing $what"
    else
      echo "❌ missing $what"
      miss=1
    fi
  }

  if [[ "$line" == public.* && "$line" != *"("* && "$line" != *" "* ]]; then
    # relation (table/view)
    rel="${line#public.}"
    kind=$(psql "$DB_URL" -Atqc "
      select relkind
      from pg_class c
      join pg_namespace n on n.oid=c.relnamespace
      where n.nspname='public' and c.relname='${rel}'
    ")
    [[ -z "$kind" ]] && report_missing "relation: $line"

  elif [[ "$line" == public.*"("*")" ]]; then
    # function: compare by ARGUMENT TYPES ONLY
    fn="${line%%(*}"; want="${line#*(}"; want="${want%)}"
    WANT="$(norm_types "$want")"            # '' for zero-arg functions

    EXIST=$(psql "$DB_URL" -Atqc "
      select oidvectortypes(p.proargtypes)
      from pg_proc p
      join pg_namespace n on n.oid=p.pronamespace
      where n.nspname='public' and p.proname='${fn#public.}'
    ")

    hit=0
    found_any=0
    while IFS= read -r types; do
      found_any=1
      T="$(norm_types "$types")"            # '' when zero-arg
      # zero-arg match: both sides are empty
      if [[ -z "$T" && -z "$WANT" ]]; then hit=1; break; fi
      # non-zero-arg match
      if [[ -n "$T" && "$T" == "$WANT" ]]; then hit=1; break; fi
    done <<< "$EXIST"

    if [[ $hit -eq 0 ]]; then
      echo "— DEBUG function $fn — wanted: [${WANT}], found:"
      if [[ $found_any -eq 0 ]]; then
        echo "  (no overloads found for ${fn#public.} in schema public)"
      else
        while IFS= read -r t; do
          echo "  - $(norm_types "$t")"
        done <<< "$EXIST"
      fi
      report_missing "function: $line"
    fi

  else
    # trigger line "schema.table  trigger_name"
    tbl="${line% *}"; trg="${line##* }"
    exists=$(psql "$DB_URL" -Atqc "
      select 1 from pg_trigger t
      where t.tgname='${trg}' and t.tgrelid='${tbl}'::regclass
      limit 1
    ")
    [[ -z "$exists" ]] && report_missing "trigger: $line"
  fi
done < "$file"

if [[ $miss -ne 0 ]]; then
  echo "Schema contract violations found. Failing."
  exit 1
fi
echo "✅ Schema contract satisfied."

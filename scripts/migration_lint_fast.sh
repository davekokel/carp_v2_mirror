#!/usr/bin/env bash
set -euo pipefail

root="supabase/migrations"

echo "== scanning $root =="
echo

rg() { grep -RniE "$1" "$root" || true; }

echo "— stray DO <digits> —"
rg '^DO[[:space:]]+[0-9]+'; echo

echo "— lone '\$ plpgsql;' terminators —"
rg '^[[:space:]]*\$[[:space:]]*plpgsql;' ; echo

echo "— END <digits> LANGUAGE plpgsql; —"
rg 'END[[:space:]]+[0-9]+[[:space:]]+LANGUAGE[[:space:]]+plpgsql[[:space:]]*;' ; echo

echo "— END LANGUAGE plpgsql; (missing $$ line) —"
rg 'END[[:space:]]+LANGUAGE[[:space:]]+plpgsql[[:space:]]*;' ; echo

echo "— pg_policies/policyname (should be pg_policy/polname) —"
rg '\bpg_policies\b|\bpolicyname\b' ; echo

echo "— schemaname/tablename filters on pg_policy (should use polrelid) —"
rg '\bschemaname\b|\btablename\b' ; echo

echo "— dynamic (::regclass) from schema||'.'||table —"
rg "\(quote_ident\(.*table_schema\).*::regclass" ; echo

echo "— transaction_timeout uses —"
rg '\btransaction_timeout\b' ; echo

echo "— bare CREATE SCHEMA util_mig —"
rg 'CREATE[[:space:]]+SCHEMA[[:space:]]+(?!IF[[:space:]]+NOT[[:space:]]+EXISTS)[[:space:]]*util_mig\b' ; echo

echo "— bare CREATE TYPE public.container_status —"
rg '^[[:space:]]*CREATE[[:space:]]+TYPE[[:space:]]+(public\.)?container_status[[:space:]]+AS[[:space:]]+ENUM' ; echo

echo "== summary =="
for pat in \
  '^DO[[:space:]]+[0-9]+' \
  '^[[:space:]]*\$[[:space:]]*plpgsql;' \
  'END[[:space:]]+[0-9]+[[:space:]]+LANGUAGE[[:space:]]+plpgsql[[:space:]]*;' \
  'END[[:space:]]+LANGUAGE[[:space:]]+plpgsql[[:space:]]*;' \
  '\bpg_policies\b|\bpolicyname\b' \
  '\bschemaname\b|\btablename\b' \
  "\(quote_ident\(.*table_schema\).*::regclass" \
  '\btransaction_timeout\b' \
  'CREATE[[:space:]]+SCHEMA[[:space:]]+(?!IF[[:space:]]+NOT[[:space:]]+EXISTS)[[:space:]]*util_mig\b' \
  '^[[:space:]]*CREATE[[:space:]]+TYPE[[:space:]]+(public\.)?container_status[[:space:]]+AS[[:space:]]+ENUM'
do
  c=$(grep -RliE "$pat" "$root" | wc -l | tr -d ' ')
  printf "%3d  %s\n" "$c" "$pat"
done

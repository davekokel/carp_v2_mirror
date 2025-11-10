set -euo pipefail
: "${DB_URL:?missing}"
OUT_DIR="supabase/audit"
mkdir -p "$OUT_DIR"

psql "$DB_URL" -Atc "select proname, pg_get_functiondef(p.oid) from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and proname in ('upsert_fish_by_identity','upsert_transgene_allele','uuid_base36_8') order by 1" > "$OUT_DIR/functions.sql"

psql "$DB_URL" -Atc "select c.relname as table_name, t.tgname as trigger_name, pg_get_triggerdef(t.oid) from pg_trigger t join pg_class c on c.oid=t.tgrelid join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and not t.tgisinternal and t.tgname in ('trg_clutch_default_treated') order by 1,2" > "$OUT_DIR/triggers.sql"

psql "$DB_URL" -Atc "select schemaname, sequencename, last_value, start_value, increment_by, max_value, min_value, cache_size, cycle from pg_sequences where schemaname='public' and sequencename in ('transgene_allele_global','treated_clutch_seq') order by 2" > "$OUT_DIR/sequences.tsv"

psql "$DB_URL" -Atc "select extname, extversion from pg_extension where extname in ('pgcrypto','uuid-ossp') order by 1" > "$OUT_DIR/extensions.tsv"

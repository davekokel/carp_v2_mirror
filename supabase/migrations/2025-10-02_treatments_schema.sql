mkdir -p supabase/migrations
FILE=supabase/migrations/2025-10-02_treatments_schema.sql
pbpaste > "$FILE"
psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$FILE"
git add "$FILE"
git commit -m "migrations: add treatments schema (enums, tables, view, checks)"
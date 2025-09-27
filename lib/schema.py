from sqlalchemy import text

ENSURE_TANK_SCHEMA_SQL = """
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tank_status') THEN
    CREATE TYPE tank_status AS ENUM ('inactive','alive','to_kill','dead');
  END IF;
END; $$;

CREATE TABLE IF NOT EXISTS public.tank_assignments(
  fish_id    uuid PRIMARY KEY REFERENCES public.fish(id) ON DELETE CASCADE,
  tank_label text NOT NULL,
  status     tank_status NOT NULL DEFAULT 'inactive'
);

CREATE INDEX IF NOT EXISTS ix_tank_assignments_status ON public.tank_assignments(status);
"""

def ensure_tank_schema(cx):
    cx.execute(text(ENSURE_TANK_SCHEMA_SQL))

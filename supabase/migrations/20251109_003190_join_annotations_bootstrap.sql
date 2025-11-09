BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- enum first (safe if already created)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='annotation_target_kind') THEN
    CREATE TYPE annotation_target_kind AS ENUM ('fish','clutch_inst','cross','tank','plasmid');
  END IF;
END$$;

-- base table (only if missing)
DO $$
BEGIN
  IF to_regclass('public.join_annotations') IS NULL THEN
    CREATE TABLE public.join_annotations (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      target_kind annotation_target_kind,
      target_id uuid,
      kind_code text,
      value_text text,
      value_num double precision,
      created_at timestamptz DEFAULT now()
    );
  END IF;
END$$;

-- helpful index (idempotent)
CREATE INDEX IF NOT EXISTS idx_join_annotations_kind_id
  ON public.join_annotations(target_kind, target_id);

COMMIT;

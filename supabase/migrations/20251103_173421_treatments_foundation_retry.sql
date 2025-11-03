BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1) Ensure treatments exists (no-op if already there)
CREATE TABLE IF NOT EXISTS public.treatments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind_code text NOT NULL,
  name text NOT NULL,
  notes text DEFAULT '',
  plasmid_code text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT treatments_kind_chk CHECK (kind_code IN ('plasmid','rna','dye','drug','other'))
);

-- 2) Ensure join_clutch_treatments.treatment_id exists (no-op if already there)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables
             WHERE table_schema='public' AND table_name='join_clutch_treatments')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns
                     WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='treatment_id')
  THEN
    EXECUTE 'ALTER TABLE public.join_clutch_treatments ADD COLUMN treatment_id uuid';
  END IF;
END$$;

-- 3) (No backfill here—left to later migrations)

-- 4) Recreate v_clutch_treatments_pretty *only if* we can detect the clutch FK column
DROP VIEW IF EXISTS public.v_clutch_treatments_pretty;

DO $$
DECLARE
  clutch_col text;
  created_expr text;
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='clutch_id') THEN
    clutch_col := 'clutch_id';
  ELSIF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='clutch_instance_id') THEN
    clutch_col := 'clutch_instance_id';
  ELSIF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='clutches_id') THEN
    clutch_col := 'clutches_id';
  ELSE
    clutch_col := NULL;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='created_at') THEN
    created_expr := 'j.created_at';
  ELSE
    created_expr := 'now()';
  END IF;

  IF clutch_col IS NOT NULL THEN
    EXECUTE format($f$
      CREATE VIEW public.v_clutch_treatments_pretty AS
      SELECT
        j.id::text AS join_id,
        j.%I::text AS clutch_id,
        t.id::text AS treatment_id,
        t.kind_code,
        t.name AS treatment_name,
        t.plasmid_code,
        t.notes AS treatment_notes,
        %s AS created_at
      FROM public.join_clutch_treatments j
      JOIN public.treatments t ON t.id=j.treatment_id;
    $f$, clutch_col, created_expr);
  ELSE
    -- Fall back to a minimal view to keep rebuilds green
    EXECUTE $f$
      CREATE VIEW public.v_clutch_treatments_pretty AS
      SELECT
        j.id::text AS join_id,
        NULL::text AS clutch_id,
        t.id::text AS treatment_id,
        t.kind_code,
        t.name AS treatment_name,
        t.plasmid_code,
        t.notes AS treatment_notes,
        now() AS created_at
      FROM public.join_clutch_treatments j
      JOIN public.treatments t ON t.id=j.treatment_id;
    $f$;
  END IF;
END$$;

COMMIT;

BEGIN;

DROP VIEW IF EXISTS public.v_clutch_treatments_pretty;

DO $$
DECLARE
  clutch_col text;
  created_col text;
  created_expr text;
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='clutch_id') THEN
    clutch_col := 'clutch_id';
  ELSIF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='clutch_instance_id') THEN
    clutch_col := 'clutch_instance_id';
  ELSIF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='clutches_id') THEN
    clutch_col := 'clutches_id';
  ELSE
    RAISE EXCEPTION 'join_clutch_treatments is missing a clutch FK column';
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='created_at') THEN
    created_col := 'created_at';
    created_expr := format('j.%I', created_col);
  ELSE
    created_expr := 'now()';
  END IF;

  EXECUTE format($f$
    CREATE OR REPLACE VIEW public.v_clutch_treatments_pretty AS
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
END$$;

COMMIT;

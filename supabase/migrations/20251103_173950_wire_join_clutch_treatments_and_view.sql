BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='join_clutch_treatments'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='treatment_id'
  ) THEN
    EXECUTE 'ALTER TABLE public.join_clutch_treatments ADD COLUMN treatment_id uuid';
  END IF;
END$$;

DO $$
DECLARE
  has_kind boolean;
  has_name boolean;
  has_plasmid boolean;
  has_notes boolean;
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='join_clutch_treatments') THEN
    SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='kind_code') INTO has_kind;
    SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='name') INTO has_name;
    SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='plasmid_code') INTO has_plasmid;
    SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='notes') INTO has_notes;

    IF has_kind AND has_name THEN
      EXECUTE '
        INSERT INTO public.treatments (kind_code, name, notes, plasmid_code)
        SELECT j.kind_code,
               j.name,
               COALESCE(' || CASE WHEN has_notes THEN 'j.notes' ELSE 'NULL' END || ', ''''),
               ' || CASE WHEN has_plasmid THEN 'j.plasmid_code' ELSE 'NULL' END || '
        FROM public.join_clutch_treatments j
        LEFT JOIN public.treatments t
          ON t.kind_code=j.kind_code
         AND t.name=j.name
         AND COALESCE(t.plasmid_code, '''')=COALESCE(' || CASE WHEN has_plasmid THEN 'j.plasmid_code' ELSE 'NULL' END || ', '''')
        WHERE t.id IS NULL
        GROUP BY j.kind_code, j.name, ' || (CASE WHEN has_plasmid THEN 'j.plasmid_code' ELSE 'NULL' END) || ', ' || (CASE WHEN has_notes THEN 'j.notes' ELSE 'NULL' END) || '
      ';

      EXECUTE '
        UPDATE public.join_clutch_treatments j
        SET treatment_id = t.id
        FROM public.treatments t
        WHERE t.kind_code=j.kind_code
          AND t.name=j.name
          AND COALESCE(t.plasmid_code, '''')=COALESCE(' || CASE WHEN has_plasmid THEN 'j.plasmid_code' ELSE 'NULL' END || ', '''')
          AND j.treatment_id IS NULL
      ';
    END IF;
  END IF;
END$$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='join_clutch_treatments') THEN
    BEGIN
      ALTER TABLE public.join_clutch_treatments
        ADD CONSTRAINT fk_join_ct_treatment
        FOREIGN KEY (treatment_id) REFERENCES public.treatments(id)
        ON UPDATE CASCADE ON DELETE RESTRICT;
    EXCEPTION WHEN duplicate_object THEN
      NULL;
    END;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='kind_code')
    THEN EXECUTE 'ALTER TABLE public.join_clutch_treatments DROP COLUMN kind_code'; END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='name')
    THEN EXECUTE 'ALTER TABLE public.join_clutch_treatments DROP COLUMN name'; END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='plasmid_code')
    THEN EXECUTE 'ALTER TABLE public.join_clutch_treatments DROP COLUMN plasmid_code'; END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='notes')
    THEN EXECUTE 'ALTER TABLE public.join_clutch_treatments DROP COLUMN notes'; END IF;
  END IF;
END$$;

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
END$$;

COMMIT;

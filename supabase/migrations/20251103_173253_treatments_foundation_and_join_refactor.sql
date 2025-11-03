BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.treatments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind_code text NOT NULL,
  name text NOT NULL,
  notes text DEFAULT '',
  plasmid_code text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT treatments_kind_chk CHECK (kind_code IN ('plasmid','rna','dye','drug','other'))
);

DO $$
DECLARE
  has_plasmids bool;
  ref_col text;
  ref_col_is_text bool;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='plasmids'
  ) INTO has_plasmids;

  IF has_plasmids THEN
    SELECT CASE
             WHEN EXISTS (
               SELECT 1 FROM information_schema.columns
               WHERE table_schema='public' AND table_name='plasmids'
                 AND column_name='plasmid_code'
             ) THEN 'plasmid_code'
             WHEN EXISTS (
               SELECT 1 FROM information_schema.columns
               WHERE table_schema='public' AND table_name='plasmids'
                 AND column_name='code'
             ) THEN 'code'
             ELSE NULL
           END
    INTO ref_col;

    IF ref_col IS NOT NULL THEN
      SELECT data_type IN ('text','character varying')
      FROM information_schema.columns
      WHERE table_schema='public' AND table_name='plasmids' AND column_name=ref_col
      INTO ref_col_is_text;

      IF ref_col_is_text THEN
        BEGIN
          EXECUTE format($f$
            ALTER TABLE public.treatments
            ADD CONSTRAINT fk_treatments_plasmid
            FOREIGN KEY (plasmid_code)
            REFERENCES public.plasmids(%I)
            ON UPDATE CASCADE ON DELETE SET NULL
          $f$, ref_col);
        EXCEPTION WHEN duplicate_object THEN
          NULL;
        END;
      END IF;
    END IF;
  END IF;
END$$;

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
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='join_clutch_treatments'
  ) THEN
    SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='treatment_type') INTO has_kind;
    SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='treatment_code') INTO has_name;
    SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='plasmid_code') INTO has_plasmid;
    SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='treatment_name') INTO has_notes;

    IF has_kind OR has_name THEN
      PERFORM 1; -- no-op; original file tried to backfill, we now leave backfill to later migrations
    END IF;
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
    clutch_col := NULL;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='created_at') THEN
    created_col := 'created_at';
    created_expr := format('j.%I', created_col);
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

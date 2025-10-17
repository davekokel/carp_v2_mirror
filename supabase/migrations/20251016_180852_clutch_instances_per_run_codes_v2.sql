-- =========================
-- Phase A: structure + backfill (no DDL that conflicts with pending events)
-- =========================
BEGIN;

-- Add columns (nullable during backfill)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='seq'
  ) THEN
    ALTER TABLE public.clutch_instances ADD COLUMN seq smallint;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='clutch_instance_code'
  ) THEN
    ALTER TABLE public.clutch_instances ADD COLUMN clutch_instance_code text;
  END IF;
END$$;

-- Per-run sequencer table
CREATE TABLE IF NOT EXISTS public.clutch_instance_seq (
  cross_instance_id uuid PRIMARY KEY,
  last integer NOT NULL
);

-- Backfill seq deterministically per run
WITH ranked AS (
  SELECT
    ci.id,
    ci.cross_instance_id,
    row_number() OVER (
      PARTITION BY ci.cross_instance_id
      ORDER BY ci.created_at NULLS LAST, ci.id
    )::smallint AS rn
  FROM public.clutch_instances ci
  WHERE ci.seq IS NULL
)
UPDATE public.clutch_instances x
SET seq = r.rn
FROM ranked r
WHERE x.id = r.id;

-- Backfill codes from seq and cross_run_code
WITH src AS (
  SELECT ci.id, ci.seq, cinst.cross_run_code
  FROM public.clutch_instances ci
  JOIN public.cross_instances cinst ON cinst.id = ci.cross_instance_id
  WHERE (ci.clutch_instance_code IS NULL OR btrim(ci.clutch_instance_code) = '')
)
UPDATE public.clutch_instances t
SET clutch_instance_code = 'XR-' || s.cross_run_code || '-' || lpad(s.seq::text, 2, '0')
FROM src s
WHERE t.id = s.id;

-- Seed sequencer to current max per run
INSERT INTO public.clutch_instance_seq(cross_instance_id, last)
SELECT ci.cross_instance_id, MAX(ci.seq)::int
FROM public.clutch_instances ci
GROUP BY ci.cross_instance_id
ON CONFLICT (cross_instance_id) DO UPDATE SET last = EXCLUDED.last;

COMMIT;

-- =========================
-- Phase B: constraints + trigger (fresh transaction, no pending events)
-- =========================
BEGIN;

-- Unique per run: (cross_instance_id, seq)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.clutch_instances'::regclass
      AND conname='uq_clutch_instances_run_seq'
  ) THEN
    ALTER TABLE public.clutch_instances
      ADD CONSTRAINT uq_clutch_instances_run_seq UNIQUE (cross_instance_id, seq);
  END IF;
END$$;

-- Unique code
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.clutch_instances'::regclass
      AND conname='uq_clutch_instances_code'
  ) THEN
    ALTER TABLE public.clutch_instances
      ADD CONSTRAINT uq_clutch_instances_code UNIQUE (clutch_instance_code);
  END IF;
END$$;

-- Not nulls now that backfill is done
ALTER TABLE public.clutch_instances
  ALTER COLUMN seq SET NOT NULL,
  ALTER COLUMN clutch_instance_code SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_clutch_instances_code
  ON public.clutch_instances(clutch_instance_code);

-- Trigger: allocate next seq per run and set code on INSERT
CREATE OR REPLACE FUNCTION public.trg_clutch_instances_alloc_seq()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_next int;
  v_run text;
BEGIN
  -- Allocate seq per cross_instance_id if not provided
  IF NEW.seq IS NULL OR NEW.seq = 0 THEN
    INSERT INTO public.clutch_instance_seq(cross_instance_id, last)
    VALUES (NEW.cross_instance_id, 0)
    ON CONFLICT (cross_instance_id) DO UPDATE
      SET last = public.clutch_instance_seq.last + 1
    RETURNING last INTO v_next;

    NEW.seq := v_next::smallint;
  END IF;

  -- Build code XR-<run>-NN
  SELECT cross_run_code INTO v_run FROM public.cross_instances WHERE id = NEW.cross_instance_id;
  NEW.clutch_instance_code := 'XR-' || v_run || '-' || lpad(NEW.seq::text, 2, '0');

  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS clutch_instances_alloc_seq ON public.clutch_instances;
CREATE TRIGGER clutch_instances_alloc_seq
BEFORE INSERT ON public.clutch_instances
FOR EACH ROW
EXECUTE FUNCTION public.trg_clutch_instances_alloc_seq();

COMMIT;

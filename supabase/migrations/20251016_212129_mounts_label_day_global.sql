-- =========================
-- Phase A: backfill labels as day-global YYYY-MM-DD-xx
-- =========================
BEGIN;

-- Ensure mount_label column exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='mounts' AND column_name='mount_label'
  ) THEN
    ALTER TABLE public.mounts ADD COLUMN mount_label text;
  END IF;
END$$;

-- Backfill: per day (mount_date), not per run
WITH ranked AS (
  SELECT
    m.id,
    to_char(m.mount_date, 'YYYY-MM-DD') AS dlabel,
    row_number() OVER (
      PARTITION BY m.mount_date
      ORDER BY COALESCE(m.time_mounted, m.mount_date::timestamptz, m.created_at) NULLS LAST, m.id
    ) AS rn
  FROM public.mounts m
  WHERE m.mount_label IS NULL OR btrim(m.mount_label) = ''
)
UPDATE public.mounts t
SET mount_label = r.dlabel || '-' || lpad(r.rn::text, 2, '0')
FROM ranked r
WHERE t.id = r.id;

COMMIT;

-- =========================
-- Phase B: constraints + trigger for day-global allocation
-- =========================
BEGIN;

-- Drop any old run-scoped label uniqueness
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.mounts'::regclass AND conname='uq_mounts_run_date_label'
  ) THEN
    ALTER TABLE public.mounts DROP CONSTRAINT uq_mounts_run_date_label;
  END IF;
END$$;

-- Enforce label uniqueness globally
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.mounts'::regclass AND conname='uq_mounts_label'
  ) THEN
    ALTER TABLE public.mounts ADD CONSTRAINT uq_mounts_label UNIQUE (mount_label);
  END IF;
END$$;

-- mount_label now required
ALTER TABLE public.mounts
  ALTER COLUMN mount_label SET NOT NULL;

-- Per-day sequencer table for day-global allocation
CREATE TABLE IF NOT EXISTS public.mount_label_seq_day (
  mount_date date PRIMARY KEY,
  last integer NOT NULL
);

-- Seed day counters from existing data
INSERT INTO public.mount_label_seq_day(mount_date, last)
SELECT m.mount_date, COUNT(*)::int
FROM public.mounts m
GROUP BY m.mount_date
ON CONFLICT (mount_date) DO UPDATE SET last = EXCLUDED.last;

-- Update trigger to allocate mount_label day-globally
CREATE OR REPLACE FUNCTION public.trg_mounts_alloc_seq()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_next int;
  v_run  text;
BEGIN
  -- Keep per-run seq for mount_code (unchanged)
  IF NEW.seq IS NULL OR NEW.seq = 0 THEN
    INSERT INTO public.mount_seq(cross_instance_id, last)
    VALUES (NEW.cross_instance_id, 0)
    ON CONFLICT (cross_instance_id) DO UPDATE
      SET last = public.mount_seq.last + 1
    RETURNING last INTO v_next;
    NEW.seq := v_next::smallint;
  END IF;

  -- Build mount_code (machine code): MT-<run>-NN
  SELECT cross_run_code INTO v_run FROM public.cross_instances WHERE id = NEW.cross_instance_id;
  NEW.mount_code := 'MT-' || v_run || '-' || lpad(NEW.seq::text, 2, '0');

  -- Allocate day-global mount_label: YYYY-MM-DD-xx
  INSERT INTO public.mount_label_seq_day(mount_date, last)
  VALUES (NEW.mount_date, 1)
  ON CONFLICT (mount_date) DO UPDATE
    SET last = public.mount_label_seq_day.last + 1
  RETURNING last INTO v_next;

  NEW.mount_label := to_char(NEW.mount_date, 'YYYY-MM-DD') || '-' || lpad(v_next::text, 2, '0');

  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS mounts_alloc_seq ON public.mounts;
CREATE TRIGGER mounts_alloc_seq
BEFORE INSERT ON public.mounts
FOR EACH ROW
EXECUTE FUNCTION public.trg_mounts_alloc_seq();

COMMIT;

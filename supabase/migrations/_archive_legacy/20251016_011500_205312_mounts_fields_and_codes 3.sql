-- =========================
-- Phase A: structure + backfill (no conflicting DDL)
-- =========================
BEGIN;

-- 1) New columns (nullable during backfill)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns  WHERE table_schema='public' AND table_name='mounts' AND column_name='time_mounted'
  ) THEN
    ALTER TABLE public.mounts ADD COLUMN time_mounted timestamptz;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns  WHERE table_schema='public' AND table_name='mounts' AND column_name='mounting_orientation'
  ) THEN
    ALTER TABLE public.mounts ADD COLUMN mounting_orientation text;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns  WHERE table_schema='public' AND table_name='mounts' AND column_name='n_top'
  ) THEN
    ALTER TABLE public.mounts ADD COLUMN n_top integer DEFAULT 0;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns  WHERE table_schema='public' AND table_name='mounts' AND column_name='n_bottom'
  ) THEN
    ALTER TABLE public.mounts ADD COLUMN n_bottom integer DEFAULT 0;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns  WHERE table_schema='public' AND table_name='mounts' AND column_name='seq'
  ) THEN
    ALTER TABLE public.mounts ADD COLUMN seq smallint;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns  WHERE table_schema='public' AND table_name='mounts' AND column_name='mount_code'
  ) THEN
    ALTER TABLE public.mounts ADD COLUMN mount_code text;
  END IF;
END$$;

-- Optional CHECKs (non-negative counts)
ALTER TABLE public.mounts
  ADD CONSTRAINT IF NOT EXISTS ck_mounts_n_top_nonneg    CHECK (n_top    IS NULL OR n_top    >= 0),
  ADD CONSTRAINT IF NOT EXISTS ck_mounts_n_bottom_nonneg CHECK (n_bottom IS NULL OR n_bottom >= 0);

-- 2) Per-run sequencer table (like for clutch_instances)
CREATE TABLE IF NOT EXISTS public.mount_seq (
  cross_instance_id uuid PRIMARY KEY,
  last integer NOT NULL
);

-- 3) Backfill seq deterministically per run
WITH ranked AS (
  SELECT
    m.id,
    m.cross_instance_id,
    row_number() OVER (
      PARTITION BY m.cross_instance_id
      ORDER BY COALESCE(m.time_mounted, m.mount_date::timestamptz, m.created_at) NULLS LAST, m.id
    )::smallint AS rn
  FROM public.mounts AS m
  WHERE m.seq IS NULL
)
UPDATE public.mounts t
SET seq = r.rn
FROM ranked AS r
WHERE t.id = r.id;

-- 4) Backfill mount_code as MT-<run>-NN
WITH src AS (
  SELECT m.id, m.seq, ci.cross_run_code AS run_code
  FROM public.mounts AS m
  JOIN public.cross_instances AS ci ON ci.id = m.cross_instance_id
  WHERE (m.mount_code IS NULL OR btrim(m.mount_code) = '')
)
UPDATE public.mounts t
SET mount_code = 'MT-' || s.run_code || '-' || lpad(s.seq::text, 2, '0')
FROM src AS s
WHERE t.id = s.id;

-- 5) Seed the sequencer to current max per run
INSERT INTO public.mount_seq(cross_instance_id, last)
SELECT m.cross_instance_id, MAX(m.seq)::int
FROM public.mounts AS m
GROUP BY m.cross_instance_id
ON CONFLICT (cross_instance_id) DO UPDATE SET last = EXCLUDED.last;

COMMIT;

-- =========================
-- Phase B: constraints + trigger (fresh transaction)
-- =========================
BEGIN;

-- Unique within a run
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint  WHERE conrelid='public.mounts'::regclass AND conname='uq_mounts_run_seq'
  ) THEN
    ALTER TABLE public.mounts
      ADD CONSTRAINT uq_mounts_run_seq UNIQUE (cross_instance_id, seq);
  END IF;
END$$;

-- Globally unique code
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint  WHERE conrelid='public.mounts'::regclass AND conname='uq_mounts_code'
  ) THEN
    ALTER TABLE public.mounts
      ADD CONSTRAINT uq_mounts_code UNIQUE (mount_code);
  END IF;
END$$;

-- Not nulls now that backfill is done
ALTER TABLE public.mounts
  ALTER COLUMN seq SET NOT NULL,
  ALTER COLUMN mount_code SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_mounts_code          ON public.mounts(mount_code);
CREATE INDEX IF NOT EXISTS ix_mounts_time_mounted  ON public.mounts(time_mounted DESC);

-- 6) Trigger to assign next seq per run & build mount_code on INSERT
CREATE OR REPLACE FUNCTION public.trg_mounts_alloc_seq()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_next int;
  v_run  text;
BEGIN
  IF NEW.seq IS NULL OR NEW.seq = 0 THEN
    INSERT INTO public.mount_seq(cross_instance_id, last)
    VALUES (NEW.cross_instance_id, 0)
    ON CONFLICT (cross_instance_id) DO UPDATE
      SET last = public.mount_seq.last + 1
    RETURNING last INTO v_next;

    NEW.seq := v_next::smallint;
  END IF;

  SELECT cross_run_code INTO v_run
  FROM public.cross_instances  WHERE id = NEW.cross_instance_id;

  NEW.mount_code := 'MT-' || v_run || '-' || lpad(NEW.seq::text, 2, '0');
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS mounts_alloc_seq ON public.mounts;
CREATE TRIGGER mounts_alloc_seq
BEFORE INSERT ON public.mounts
FOR EACH ROW
EXECUTE FUNCTION public.trg_mounts_alloc_seq();

COMMIT;

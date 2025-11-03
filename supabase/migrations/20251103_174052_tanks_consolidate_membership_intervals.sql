BEGIN;

CREATE EXTENSION IF NOT EXISTS btree_gist;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='valid_from'
  ) THEN
    EXECUTE 'ALTER TABLE public.join_fish_tanks ADD COLUMN valid_from timestamptz';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='valid_to'
  ) THEN
    EXECUTE 'ALTER TABLE public.join_fish_tanks ADD COLUMN valid_to timestamptz';
  END IF;
END$$;

UPDATE public.join_fish_tanks
SET
  valid_from = COALESCE(valid_from, since, now()),
  valid_to   = COALESCE(valid_to, until)
WHERE valid_from IS NULL
   OR (valid_to IS NULL AND until IS NOT NULL);

DO $$
BEGIN
  ALTER TABLE public.join_fish_tanks
    ALTER COLUMN valid_from SET NOT NULL;
EXCEPTION WHEN others THEN
  NULL;
END$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_jft_one_open_per_fish
  ON public.join_fish_tanks(fish_id)
  WHERE valid_to IS NULL;

DO $$
BEGIN
  ALTER TABLE public.join_fish_tanks
    ADD CONSTRAINT ex_jft_no_overlap
    EXCLUDE USING gist (
      fish_id WITH =,
      tstzrange(valid_from, COALESCE(valid_to, 'infinity'::timestamptz), '[)') WITH &&
    );
EXCEPTION WHEN duplicate_object THEN
  NULL;
END$$;

COMMIT;

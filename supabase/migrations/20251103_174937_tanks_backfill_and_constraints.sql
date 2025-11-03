BEGIN;

CREATE EXTENSION IF NOT EXISTS btree_gist;

UPDATE public.join_fish_tanks
SET
  valid_from = COALESCE(valid_from, since, now()),
  valid_to   = COALESCE(valid_to, until)
WHERE valid_from IS NULL
   OR (valid_to IS NULL AND until IS NOT NULL);

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

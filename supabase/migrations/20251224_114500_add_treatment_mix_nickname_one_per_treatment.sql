BEGIN;

ALTER TABLE public.treatment_mixes
  ADD COLUMN IF NOT EXISTS mix_nickname text;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'treatment_mixes_one_per_treatment_uniq'
  ) THEN
    ALTER TABLE public.treatment_mixes
      ADD CONSTRAINT treatment_mixes_one_per_treatment_uniq UNIQUE (treatment_id);
  END IF;
END $$;

INSERT INTO public.treatment_mixes (id, treatment_id, mix_code, notes, created_at)
SELECT
  gen_random_uuid(),
  t.id,
  'M1',
  'autofill: ensure 1 mix per treatment',
  now()
FROM public.treatments t
LEFT JOIN public.treatment_mixes tm ON tm.treatment_id = t.id
WHERE tm.id IS NULL;

COMMIT;

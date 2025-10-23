BEGIN;

-- 1) De-dupe: keep newest per (mom, dad), delete older ones
WITH ranked AS (
  SELECT fish_pair_id,
         mom_fish_code, dad_fish_code, created_at,
         row_number() OVER (PARTITION BY mom_fish_code, dad_fish_code ORDER BY created_at DESC, fish_pair_id DESC) AS rn
  FROM public.fish_pairs
)
DELETE FROM public.fish_pairs fp
USING ranked r
WHERE fp.fish_pair_id = r.fish_pair_id
  AND r.rn > 1;

-- 2) Backfill fish_pair_code where NULL
WITH nextnum AS (
  SELECT COALESCE(MAX((regexp_match(fish_pair_code, '^FP-\d{2}(\d{4})$'))[1]::int), 0) AS n
  FROM public.fish_pairs
)
UPDATE public.fish_pairs fp
SET fish_pair_code =
  'FP-'||to_char(EXTRACT(YEAR FROM now())::int % 100, 'FM00')||
  lpad((SELECT n + ROW_NUMBER() OVER (ORDER BY fp.fish_pair_id)
        FROM nextnum) ::text, 4, '0')
WHERE fish_pair_code IS NULL;

-- 3) Enforce uniqueness on the ordered pair (Mom, Dad)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fish_pairs_mom_dad_unique'
      AND conrelid='public.fish_pairs'::regclass
  ) THEN
    ALTER TABLE public.fish_pairs
      ADD CONSTRAINT fish_pairs_mom_dad_unique
      UNIQUE (mom_fish_code, dad_fish_code);
  END IF;
END$$;

COMMIT;

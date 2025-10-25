BEGIN;
-- backfill missing fish_pair_code on tank_pairs from the newest fish_pairs row (safe for empty)
WITH last_fp AS (
  SELECT fish_pair_code FROM public.fish_pairs 
  WHERE fish_pair_code IS NOT NULL 
  ORDER BY created_at DESC LIMIT 1
)
UPDATE public.tank_pairs tp
SET fish_pair_code = (SELECT fish_pair_code FROM last_fp)
WHERE fish_pair_code IS NULL AND EXISTS (SELECT 1 FROM last_fp);

-- backfill missing tank_pair_code using generator when fish_pair_code is present
UPDATE public.tank_pairs
SET tank_pair_code = public.make_tp_code(fish_pair_code)
WHERE tank_pair_code IS NULL AND COALESCE(fish_pair_code,'') <> '';
COMMIT;

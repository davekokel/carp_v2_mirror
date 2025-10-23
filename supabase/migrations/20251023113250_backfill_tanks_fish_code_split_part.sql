BEGIN;
WITH parsed AS (
  SELECT
    t.tank_id,
    split_part(replace(trim(t.tank_code),'TANK-',''), '-#', 1) AS fish_code_parsed
  FROM public.tanks t
  WHERE t.fish_code IS NULL
),
valid AS (
  SELECT p.tank_id, p.fish_code_parsed
  FROM parsed p
  JOIN public.fish f ON f.fish_code = p.fish_code_parsed
)
UPDATE public.tanks t
SET fish_code = v.fish_code_parsed
FROM valid v
WHERE t.tank_id = v.tank_id
  AND t.fish_code IS NULL;

DO $$
DECLARE remaining int;
BEGIN
  SELECT count(*) INTO remaining FROM public.tanks WHERE fish_code IS NULL;
  IF remaining = 0 THEN
    EXECUTE 'ALTER TABLE public.tanks ALTER COLUMN fish_code SET NOT NULL';
  END IF;
END$$;
COMMIT;

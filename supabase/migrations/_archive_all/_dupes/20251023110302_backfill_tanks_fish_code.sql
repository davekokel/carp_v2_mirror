BEGIN;

-- Parse fish_code as the substring between 'TANK-' and the trailing '-#<n>'
-- Example: TANK-FSH-250004-#1  -> FSH-250004
WITH parsed AS (
  SELECT
    t.tank_id,
    regexp_replace(t.tank_code, '^TANK-([^#]+)-#\\d+$', '\1') AS fish_code_parsed
  FROM public.tanks t
  WHERE t.fish_code IS NULL
)
UPDATE public.tanks t
SET fish_code = p.fish_code_parsed
FROM parsed p
JOIN public.fish f ON f.fish_code = p.fish_code_parsed
WHERE t.tank_id = p.tank_id
  AND t.fish_code IS NULL;

COMMIT;

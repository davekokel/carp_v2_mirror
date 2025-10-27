BEGIN;

-- 1) If a legacy twin exists for the same fish+N, DELETE the hyphen row
DELETE FROM public.tanks t
USING public.tanks l
WHERE t.tank_code ~ '^TANK-[A-Za-z0-9-]+#[0-9]+$'
  AND l.tank_code =
      'TANK(' ||
      regexp_replace(t.tank_code, '^TANK-([A-Za-z0-9-]+)#([0-9]+)$', '\1') ||
      ')#' ||
      regexp_replace(t.tank_code, '^TANK-([A-Za-z0-9-]+)#([0-9]+)$', '\2');

-- 2) If no legacy twin exists, CONVERT the hyphen row to legacy format
UPDATE public.tanks t
SET tank_code =
    'TANK(' ||
    regexp_replace(t.tank_code, '^TANK-([A-Za-z0-9-]+)#([0-9]+)$', '\1') ||
    ')#' ||
    regexp_replace(t.tank_code, '^TANK-([A-Za-z0-9-]+)#([0-9]+)$', '\2')
WHERE t.tank_code ~ '^TANK-[A-Za-z0-9-]+#[0-9]+$'
  AND NOT EXISTS (
    SELECT 1 FROM public.tanks l
    WHERE l.tank_code =
      'TANK(' ||
      regexp_replace(t.tank_code, '^TANK-([A-Za-z0-9-]+)#([0-9]+)$', '\1') ||
      ')#' ||
      regexp_replace(t.tank_code, '^TANK-([A-Za-z0-9-]+)#([0-9]+)$', '\2')
  );

COMMIT;

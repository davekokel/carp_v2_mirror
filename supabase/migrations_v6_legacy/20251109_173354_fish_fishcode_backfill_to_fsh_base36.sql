BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 0) Helper: uuid_base36_8(u uuid) -> 'FSH-XXXXXXXX' (lower 40 bits base36), guarded
CREATE OR REPLACE FUNCTION public.uuid_base36_8(u uuid)
RETURNS text
LANGUAGE plpgsql
AS $fn$
DECLARE
  hex text := replace(u::text,'-','');
  h10 text := right(hex, 10);
  n   numeric := 0;
  i   int;
  c   text;
  v   int;
  alphabet constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  out text := '';
BEGIN
  FOR i IN 1..length(h10) LOOP
    c := substr(h10, i, 1);
    v := CASE c
           WHEN '0' THEN 0 WHEN '1' THEN 1 WHEN '2' THEN 2 WHEN '3' THEN 3
           WHEN '4' THEN 4 WHEN '5' THEN 5 WHEN '6' THEN 6 WHEN '7' THEN 7
           WHEN '8' THEN 8 WHEN '9' THEN 9
           WHEN 'a' THEN 10 WHEN 'b' THEN 11 WHEN 'c' THEN 12 WHEN 'd' THEN 13
           WHEN 'e' THEN 14 WHEN 'f' THEN 15
           WHEN 'A' THEN 10 WHEN 'B' THEN 11 WHEN 'C' THEN 12 WHEN 'D' THEN 13
           WHEN 'E' THEN 14 WHEN 'F' THEN 15
           ELSE 0
         END;
    n := n*16 + v;
  END LOOP;

  FOR i IN 1..8 LOOP
    v := mod(n, 36);
    out := substr(alphabet, v+1, 1) || out;
    n := trunc(n/36);
  END LOOP;

  RETURN 'FSH-' || out;
END
$fn$;

-- 1) Backfill fish_code to FSH-XXXXXXXX where not already in desired format
--    Desired pattern: ^FSH-[0-9A-Z]{8}$
WITH to_fix AS (
  SELECT id
  FROM public.fish
  WHERE fish_code !~ '^(FSH-[0-9A-Z]{8})$' OR fish_code IS NULL
)
UPDATE public.fish f
SET fish_code = public.uuid_base36_8(f.id)
FROM to_fix t
WHERE f.id = t.id;

-- 2) Ensure a unique constraint on fish_code (guarded)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='fish'
      AND constraint_type='UNIQUE' AND constraint_name='uq_fish_fish_code'
  ) THEN
    -- guard against duplicates (should not happen because base36(uuid) is unique)
    IF NOT EXISTS (
      SELECT fish_code FROM public.fish GROUP BY fish_code HAVING COUNT(*) > 1
    ) THEN
      EXECUTE 'ALTER TABLE public.fish ADD CONSTRAINT uq_fish_fish_code UNIQUE (fish_code)';
    END IF;
  END IF;
END$$;

-- 3) (Optional) Ensure a tank per fish with new label 'TANK(FSH-XXXXXXXX)#1' (idempotent).
--    We *insert* the desired code if missing; we do NOT drop/modify existing tanks.
CREATE TABLE IF NOT EXISTS public.tanks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_code text UNIQUE NOT NULL,
  status text NOT NULL DEFAULT 'active',
  created_at timestamptz DEFAULT now()
);

WITH want AS (
  SELECT id AS fish_id, public.uuid_base36_8(id) AS fsh_code
  FROM public.fish
),
desired AS (
  SELECT 'TANK('||fsh_code||')#1'::text AS tank_code
  FROM want
)
INSERT INTO public.tanks (tank_code, status)
SELECT d.tank_code, 'active'
FROM desired d
LEFT JOIN public.tanks t ON t.tank_code = d.tank_code
WHERE t.tank_code IS NULL;

COMMIT;

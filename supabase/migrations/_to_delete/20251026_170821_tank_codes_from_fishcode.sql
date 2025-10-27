BEGIN;

-- 1) Ensure tank_code exists and is unique-ish
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tanks' AND column_name='tank_code'
  ) THEN
    ALTER TABLE public.tanks ADD COLUMN tank_code text;
  END IF;
END$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_tanks_tank_code
  ON public.tanks(tank_code)
  WHERE tank_code IS NOT NULL;

-- 2) Helper: next tank number for a fish_code based on existing TANK-<code>#N rows
CREATE OR REPLACE FUNCTION public.next_tank_num_for_fish(p_fish_code text)
RETURNS int
LANGUAGE sql
AS $$
  SELECT COALESCE(MAX( (regexp_replace(t.tank_code, '.*#', '')::int) ), 0) + 1
  FROM public.tanks t
  WHERE t.tank_code LIKE ('TANK-' || p_fish_code || '#%')
$$;

CREATE OR REPLACE FUNCTION public.make_tank_code_for_fish(p_fish_code text)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE n int;
BEGIN
  n := public.next_tank_num_for_fish(p_fish_code);
  RETURN 'TANK-' || p_fish_code || '#' || n::text;
END
$$;

-- 3) Redefine counts: count active tanks by tank_code pattern, no membership dependency
CREATE OR REPLACE VIEW public.v_fish_current_tank_counts AS
SELECT
  f.fish_uuid,
  COALESCE((
    SELECT COUNT(*) FROM public.tanks t
    WHERE t.status = 'active'
      AND t.tank_code LIKE ('TANK-' || f.fish_code || '#%')
  ), 0)::int AS current_tanks
FROM public.fish f;

-- 4) Update the fish→auto-tank trigger to assign tank_code using the fish_code
CREATE OR REPLACE FUNCTION public.fish_auto_tank()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE v_code text;
BEGIN
  -- Create exactly one active tank on insert
  v_code := public.make_tank_code_for_fish(NEW.fish_code);
  INSERT INTO public.tanks(status, tank_code) VALUES ('active', v_code);
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_fish_auto_tank ON public.fish;
CREATE TRIGGER trg_fish_auto_tank
AFTER INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.fish_auto_tank();

-- 5) Backfill: for any fish with no matching TANK-<FISH_CODE>#*, create #1
INSERT INTO public.tanks(status, tank_code)
SELECT 'active', 'TANK-' || f.fish_code || '#1'
FROM public.fish f
LEFT JOIN LATERAL (
  SELECT 1 FROM public.tanks t
  WHERE t.tank_code LIKE ('TANK-' || f.fish_code || '#%')
  LIMIT 1
) has ON true
WHERE has IS NULL;

COMMIT;

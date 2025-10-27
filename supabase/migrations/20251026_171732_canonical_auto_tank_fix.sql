BEGIN;

-- Clean out legacy auto-create functions/triggers so only one path remains
DO $$BEGIN
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='fn_fish_autocreate_tank_v2' AND pronamespace='public'::regnamespace) THEN
    DROP FUNCTION public.fn_fish_autocreate_tank_v2() CASCADE;
  END IF;
EXCEPTION WHEN undefined_function THEN NULL; END$$;

DROP TRIGGER IF EXISTS trg_fish_auto_tank ON public.fish;

-- Helper: compute next candidate N for legacy code
CREATE OR REPLACE FUNCTION public.next_tank_num_for_fish(p_fish_code text)
RETURNS int
LANGUAGE sql
AS $$
  SELECT COALESCE(MAX( (regexp_replace(t.tank_code, '.*#', '')::int) ), 0) + 1
  FROM public.tanks t
  WHERE t.tank_code LIKE ('TANK(' || p_fish_code || ')#%')
$$;

-- Canonical creator: race-safe; returns the created/ensured tank_code
CREATE OR REPLACE FUNCTION public.ensure_active_tank_for_fish(p_fish_code text)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_code text;
  v_try int;
BEGIN
  -- If one already exists, return it
  SELECT t.tank_code INTO v_code
  FROM public.tanks t
  WHERE t.status='active' AND t.tank_code LIKE ('TANK('||p_fish_code||')#%')
  ORDER BY t.tank_code
  LIMIT 1;
  IF v_code IS NOT NULL THEN
    RETURN v_code;
  END IF;

  -- Otherwise loop until we win the unique race
  FOR v_try IN 1..100 LOOP
    v_code := 'TANK(' || p_fish_code || ')#' || public.next_tank_num_for_fish(p_fish_code)::text;
    BEGIN
      INSERT INTO public.tanks(status, tank_code) VALUES ('active', v_code);
      RETURN v_code;
    EXCEPTION WHEN unique_violation THEN
      -- someone else took it; try again
      CONTINUE;
    END;
  END LOOP;

  RAISE EXCEPTION 'Could not allocate tank for fish_code=% after 100 attempts', p_fish_code;
END
$$;

-- Single canonical trigger that uses the helper
CREATE OR REPLACE FUNCTION public.fish_auto_tank()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  PERFORM public.ensure_active_tank_for_fish(NEW.fish_code);
  RETURN NEW;
END
$$;

ALTER FUNCTION public.fish_auto_tank() OWNER TO CURRENT_USER;

CREATE TRIGGER trg_fish_auto_tank
AFTER INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.fish_auto_tank();

-- Backfill: ensure exactly one active legacy-form tank per fish
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT f.fish_code
    FROM public.fish f
    LEFT JOIN LATERAL (
      SELECT 1 FROM public.tanks t
      WHERE t.status='active' AND t.tank_code LIKE ('TANK('||f.fish_code||')#%')
      LIMIT 1
    ) has ON true
    WHERE has IS NULL
  LOOP
    PERFORM public.ensure_active_tank_for_fish(r.fish_code);
  END LOOP;
END
$$;

COMMIT;

BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='chk_tanks_tank_code_format' AND conrelid='public.tanks'::regclass
  ) THEN
    ALTER TABLE public.tanks DROP CONSTRAINT chk_tanks_tank_code_format;
  END IF;
END$$;

ALTER TABLE public.tanks
  ADD CONSTRAINT chk_tanks_tank_code_format
  CHECK (tank_code IS NULL OR tank_code ~ '^TANK\([A-Za-z0-9-]+\)#[0-9]+$');

CREATE OR REPLACE FUNCTION public.next_tank_num_for_fish(p_fish_code text)
RETURNS int
LANGUAGE sql
AS $$
  SELECT COALESCE(MAX((regexp_replace(t.tank_code, '.*#', '')::int)), 0) + 1
  FROM public.tanks t
  WHERE t.tank_code LIKE ('TANK(' || p_fish_code || ')#%')
$$;

CREATE OR REPLACE FUNCTION public.make_tank_code_for_fish(p_fish_code text)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE n int;
BEGIN
  n := public.next_tank_num_for_fish(p_fish_code);
  RETURN 'TANK(' || p_fish_code || ')#' || n::text;
END
$$;

CREATE OR REPLACE VIEW public.v_fish_current_tank_counts AS
SELECT
  f.fish_uuid,
  COALESCE((
    SELECT COUNT(*) FROM public.tanks t
    WHERE t.status = 'active'
      AND t.tank_code LIKE ('TANK(' || f.fish_code || ')#%')
  ), 0)::int AS current_tanks
FROM public.fish f;

CREATE OR REPLACE FUNCTION public.fish_auto_tank()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE v_code text;
BEGIN
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

DO $$
DECLARE
  r record;
  desired text;
  exists_code boolean;
  nextn int;
BEGIN
  FOR r IN
    SELECT tank_uuid, tank_code
    FROM public.tanks
    WHERE tank_code ~ '^TANK-[A-Za-z0-9-]+#[0-9]+$'
    ORDER BY tank_code
  LOOP
    desired := 'TANK(' ||
               regexp_replace(r.tank_code, '^TANK-([A-Za-z0-9-]+)#([0-9]+)$', '\1') ||
               ')#' ||
               regexp_replace(r.tank_code, '^TANK-([A-Za-z0-9-]+)#([0-9]+)$', '\2');

    SELECT EXISTS(SELECT 1 FROM public.tanks t WHERE t.tank_code = desired AND t.tank_uuid <> r.tank_uuid)
    INTO exists_code;

    IF NOT exists_code THEN
      UPDATE public.tanks SET tank_code = desired WHERE tank_uuid = r.tank_uuid;
    ELSE
      SELECT public.next_tank_num_for_fish(regexp_replace(r.tank_code, '^TANK-([A-Za-z0-9-]+)#([0-9]+)$', '\1'))
      INTO nextn;
      UPDATE public.tanks
      SET tank_code = 'TANK(' ||
                      regexp_replace(r.tank_code, '^TANK-([A-Za-z0-9-]+)#([0-9]+)$', '\1') ||
                      ')#' || nextn::text
      WHERE tank_uuid = r.tank_uuid;
    END IF;
  END LOOP;
END
$$;

COMMIT;

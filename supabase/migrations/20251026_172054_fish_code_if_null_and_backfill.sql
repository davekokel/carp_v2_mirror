BEGIN;

-- Use a simple, durable generator when fish_code is missing.
-- Hex is fine and compact: FSH-<HEX>.
CREATE SEQUENCE IF NOT EXISTS public.fish_code_seq START 250000;

CREATE OR REPLACE FUNCTION public.bi_set_fish_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.fish_code IS NOT NULL AND btrim(NEW.fish_code) <> '' THEN
    RETURN NEW;  -- respect provided code
  END IF;

  NEW.fish_code := 'FSH-' || upper(to_hex(nextval('public.fish_code_seq')));
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_fish_before_insert_code ON public.fish;
CREATE TRIGGER trg_fish_before_insert_code
BEFORE INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.bi_set_fish_code();

-- Ensure every fish has exactly one active legacy-format tank code
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

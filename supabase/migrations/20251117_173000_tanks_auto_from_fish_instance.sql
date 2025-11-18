BEGIN;

DO $$
BEGIN
  IF to_regclass('public.fish_instance') IS NULL
     OR to_regclass('public.tanks') IS NULL THEN
    RAISE NOTICE 'fish_instance or tanks table missing; skipping tanks auto-from-fish_instance setup';
    RETURN;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.proname = 'trg_fish_instance_auto_tank'
  ) THEN
    CREATE FUNCTION public.trg_fish_instance_auto_tank()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $func$
    DECLARE
      base text;
      max_n int;
      next_n int;
      v_tank_id public.tanks.id%TYPE;
    BEGIN
      IF NEW.fish_code IS NULL OR NEW.fish_code = '' THEN
        RETURN NEW;
      END IF;

      base := 'TANK(' || NEW.fish_code || ')#';

      SELECT COALESCE(MAX(
        NULLIF(
          regexp_replace(t.tank_code, '^.*#([0-9]+)$', '\1'),
          ''
        )::int
      ), 0)
      INTO max_n
      FROM public.tanks t
      WHERE t.tank_code LIKE base || '%';

      next_n := max_n + 1;

      INSERT INTO public.tanks (tank_code, status)
      VALUES (
        base || LPAD(next_n::text, 2, '0'),
        'active'
      )
      RETURNING id INTO v_tank_id;

      IF to_regclass('public.tank_memberships') IS NOT NULL THEN
        INSERT INTO public.tank_memberships (tank_id, fish_id, role)
        VALUES (v_tank_id, NEW.id, 'resident');
      END IF;

      RETURN NEW;
    END;
    $func$;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_trigger
    WHERE tgrelid = 'public.fish_instance'::regclass
      AND tgname = 'trg_fish_instance_auto_tank'
  ) THEN
    CREATE TRIGGER trg_fish_instance_auto_tank
    AFTER INSERT ON public.fish_instance
    FOR EACH ROW
    WHEN (NEW.fish_code IS NOT NULL)
    EXECUTE FUNCTION public.trg_fish_instance_auto_tank();
  END IF;
END;
$$;

COMMIT;

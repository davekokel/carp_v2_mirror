BEGIN;

-- Drop either trigger spelling if present on public.fish
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_trigger t
    JOIN pg_class c ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = 'fish' AND t.tgname = 'trg_fish_auto_tank'
  ) THEN
    EXECUTE 'DROP TRIGGER trg_fish_auto_tank ON public.fish';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM pg_trigger t
    JOIN pg_class c ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = 'fish' AND t.tgname = 'trg_fish_autotank'
  ) THEN
    EXECUTE 'DROP TRIGGER trg_fish_autotank ON public.fish';
  END IF;
END $$;

-- Remove the function; CASCADE to clean any lingering dependencies
DROP FUNCTION IF EXISTS public.fn_fish_autocreate_tank_v2() CASCADE;

COMMIT;

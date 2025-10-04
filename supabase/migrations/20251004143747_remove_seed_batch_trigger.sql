BEGIN;

-- Keep table & FK; just drop the trigger to avoid timing/connection issues
DROP TRIGGER IF EXISTS tg_upsert_fish_seed_maps ON public.load_log_fish;

-- Keep the function around (harmless), or drop it if you prefer:
-- DROP FUNCTION IF EXISTS public.tg_upsert_fish_seed_maps();

COMMIT;

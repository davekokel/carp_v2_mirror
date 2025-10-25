DO $$
BEGIN
  -- Skip cleanly if log table isn't present
  IF to_regclass('public.load_log_fish') IS NULL THEN
    RAISE NOTICE 'Skip: public.load_log_fish missing';
    RETURN;
  END IF;

  -- Ensure mapping table exists
  IF to_regclass('public.fish_seed_batches') IS NULL THEN
    CREATE TABLE public.fish_seed_batches(
      fish_id uuid PRIMARY KEY REFERENCES public.fish(id) ON DELETE CASCADE,
      seed_batch_id text
    );
  END IF;

  -- Drop old trigger/function if they exist
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = '_upsert_fish_seed_maps' AND pronamespace = 'public'::regnamespace) THEN
    DROP FUNCTION public._upsert_fish_seed_maps();
  END IF;
  DROP TRIGGER IF EXISTS trg_upsert_fish_seed_maps ON public.load_log_fish;

  -- Create/replace function and trigger
  CREATE OR REPLACE FUNCTION public._upsert_fish_seed_maps()
  RETURNS trigger
  LANGUAGE plpgsql
  AS $FN$
  BEGIN
    IF NEW.fish_id IS NOT NULL AND NEW.seed_batch_id IS NOT NULL THEN
      INSERT INTO public.fish_seed_batches (fish_id, seed_batch_id)
      VALUES (NEW.fish_id, NEW.seed_batch_id)
      ON CONFLICT (fish_id) DO UPDATE
        SET seed_batch_id = EXCLUDED.seed_batch_id;
    END IF;
    RETURN NEW;
  END
  $FN$;

  CREATE TRIGGER trg_upsert_fish_seed_maps
  AFTER INSERT ON public.load_log_fish
  FOR EACH ROW
  EXECUTE FUNCTION public._upsert_fish_seed_maps();
END
$$;

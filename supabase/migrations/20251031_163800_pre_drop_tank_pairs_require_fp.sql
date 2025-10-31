DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname = 'tank_pairs_require_fp'
      AND tgrelid = 'public.tank_pairs'::regclass
      AND NOT tgisinternal
  ) THEN
    EXECUTE 'DROP TRIGGER tank_pairs_require_fp ON public.tank_pairs';
  END IF;

  IF EXISTS (
    SELECT 1 FROM pg_proc
    WHERE proname = 'trg_tank_pairs_require_fp'
      AND pronamespace = 'public'::regnamespace
  ) THEN
    EXECUTE 'DROP FUNCTION public.trg_tank_pairs_require_fp() CASCADE';
  END IF;
END $$;

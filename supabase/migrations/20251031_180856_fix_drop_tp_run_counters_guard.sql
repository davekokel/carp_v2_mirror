-- Guarded cleanup: remove any leftover tp_run_counters in either schema
DO $$
BEGIN
  IF to_regclass('public.tp_run_counters') IS NOT NULL THEN
    EXECUTE 'DROP TABLE IF EXISTS public.tp_run_counters CASCADE';
  END IF;

  IF to_regclass('trash_carp.tp_run_counters') IS NOT NULL THEN
    EXECUTE 'DROP TABLE IF EXISTS trash_carp.tp_run_counters CASCADE';
  END IF;
END $$;

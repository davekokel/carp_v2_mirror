BEGIN;
DO $$
DECLARE cnt int;
BEGIN
  SELECT count(*) INTO cnt
  FROM information_schema.view_table_usage
  WHERE view_schema='public' AND table_name='v_tanks_current_status';
  IF cnt=0 THEN
    EXECUTE 'drop view if exists public.v_tanks_current_status';
  END IF;
END$$;
COMMIT;

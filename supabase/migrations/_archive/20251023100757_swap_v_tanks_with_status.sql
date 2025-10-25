BEGIN;

DO $$
DECLARE cnt int;
BEGIN
  SELECT count(*) INTO cnt
  FROM information_schema.view_table_usage
  WHERE view_schema='public' AND table_name='v_tanks';
  IF cnt=0 THEN
    EXECUTE 'drop view if exists public.v_tanks';
  ELSE
    RAISE EXCEPTION 'Cannot drop v_tanks; still referenced by: % dependent view(s)', cnt;
  END IF;
END$$;

ALTER VIEW public.v_tanks_current_status RENAME TO v_tanks;

CREATE OR REPLACE VIEW public.v_tanks_current_status AS
SELECT * FROM public.v_tanks;

COMMIT;

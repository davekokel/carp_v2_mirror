BEGIN;

DO $$
DECLARE
  def text;
  others int;
BEGIN
  IF to_regclass('public.v_tanks_current_status') IS NULL THEN
    RAISE NOTICE 'v_tanks_current_status not found; nothing to do';
  ELSE
    def := pg_get_viewdef('public.v_tanks_current_status'::regclass, true);
    EXECUTE 'create or replace view public.v_tanks as ' || def;

    SELECT count(*) INTO others
    FROM information_schema.view_table_usage
    WHERE view_schema='public'
      AND table_name='v_tanks_current_status'
      AND view_name <> 'v_tanks';

    IF others = 0 THEN
      EXECUTE 'drop view if exists public.v_tanks_current_status';
    ELSE
      RAISE NOTICE 'Not dropping v_tanks_current_status; still referenced by % other view(s)', others;
    END IF;
  END IF;
END$$;

COMMIT;

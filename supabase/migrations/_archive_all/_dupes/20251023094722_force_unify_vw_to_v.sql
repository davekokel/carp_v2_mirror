BEGIN;

DROP EVENT TRIGGER IF EXISTS enforce_public_view_prefix;
DROP FUNCTION IF EXISTS public.enforce_view_prefix_v();

DO $$
DECLARE
  def text;
  def_new text;
BEGIN
  IF to_regclass('public.v_fish_overview_with_label') IS NULL
     AND to_regclass('public.vw_fish_overview_with_label') IS NOT NULL THEN
    def := pg_get_viewdef('public.vw_fish_overview_with_label'::regclass, true);
    EXECUTE 'create or replace view public.v_fish_overview_with_label as ' || def;
  END IF;

  IF to_regclass('public.v_plasmids_overview') IS NULL
     AND to_regclass('public.vw_plasmids_overview') IS NOT NULL THEN
    def := pg_get_viewdef('public.vw_plasmids_overview'::regclass, true);
    EXECUTE 'create or replace view public.v_plasmids_overview as ' || def;
  END IF;

  IF to_regclass('public.v_fish_standard') IS NULL
     AND to_regclass('public.vw_fish_standard') IS NOT NULL THEN
    def := pg_get_viewdef('public.vw_fish_standard'::regclass, true);
    def := regexp_replace(def, '("public"\\.)?(")?vw_fish_overview_with_label(")?', 'public.v_fish_overview_with_label', 'gi');
    EXECUTE 'create or replace view public.v_fish_standard as ' || def;
  END IF;

  IF to_regclass('public.v_plasmids') IS NOT NULL THEN
    def := pg_get_viewdef('public.v_plasmids'::regclass, true);
    def_new := regexp_replace(def, '("public"\\.)?(")?vw_plasmids_overview(")?', 'public.v_plasmids_overview', 'gi');
    IF def_new IS DISTINCT FROM def THEN
      EXECUTE 'create or replace view public.v_plasmids as ' || def_new;
    END IF;
  END IF;
END$$;

DROP VIEW IF EXISTS public.vw_fish_standard;

DO $$
DECLARE
  leftovers text[];
BEGIN
  SELECT array_agg(distinct vtu.view_name)
  INTO leftovers
  FROM information_schema.view_table_usage vtu
  WHERE vtu.view_schema='public'
    AND vtu.table_name IN ('vw_fish_overview_with_label','vw_plasmids_overview');
  IF leftovers IS NOT NULL THEN
    RAISE EXCEPTION 'Cannot drop vw_*; still referenced by: %', leftovers;
  END IF;
END$$;

DROP VIEW IF EXISTS public.vw_plasmids_overview;
DROP VIEW IF EXISTS public.vw_fish_overview_with_label;

CREATE FUNCTION public.enforce_view_prefix_v() RETURNS event_trigger
LANGUAGE plpgsql
AS $$
DECLARE rec record;
BEGIN
  FOR rec IN SELECT * FROM pg_event_trigger_ddl_commands() LOOP
    IF rec.object_type = 'view'
       AND rec.schema_name = 'public'
       AND rec.object_identity ~* E'^public\\.vw_' THEN
      RAISE EXCEPTION 'Disallowed view prefix vw_: %', rec.object_identity;
    END IF;
  END LOOP;
END
$$;

CREATE EVENT TRIGGER enforce_public_view_prefix
ON ddl_command_end
WHEN TAG IN ('CREATE VIEW','CREATE MATERIALIZED VIEW','ALTER VIEW','ALTER VIEW ALL IN SCHEMA')
EXECUTE PROCEDURE public.enforce_view_prefix_v();

COMMIT;

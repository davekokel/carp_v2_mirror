BEGIN;

CREATE TEMP TABLE _rename_map(old TEXT, new TEXT) ON COMMIT DROP;
INSERT INTO _rename_map(old,new) VALUES
  ('vw_fish_overview_with_label','v_fish_overview_with_label'),
  ('vw_fish_standard','v_fish_standard'),
  ('vw_plasmids_overview','v_plasmids_overview');

DO $$
DECLARE
  r RECORD;
  def TEXT;
  def_new TEXT;
BEGIN
  FOR r IN
    SELECT v.schemaname, v.viewname
    FROM pg_views v
    WHERE v.schemaname='public'
  LOOP
    def := pg_get_viewdef((quote_ident(r.schemaname)||'.'||quote_ident(r.viewname))::regclass, true);

    def_new := def;
    SELECT
      def_new := regexp_replace(def_new, '(^|[^A-Za-z0-9_])'||quote_literal(m.old)||'([^A-Za-z0-9_]|$)', '\1'||m.new||'\2', 'g')
    FROM _rename_map m;

    SELECT
      def_new := regexp_replace(def_new, '(^|[^A-Za-z0-9_])public\.'||quote_literal(m.old)||'([^A-Za-z0-9_]|$)', '\1public.'||m.new||'\2', 'g')
    FROM _rename_map m;

    IF def_new IS DISTINCT FROM def THEN
      EXECUTE 'create or replace view '
              || quote_ident(r.schemaname) || '.' || quote_ident(r.viewname)
              || ' as ' || def_new;
    END IF;
  END LOOP;
END$$;

DO $$
DECLARE
  leftovers TEXT[];
BEGIN
  SELECT array_agg(DISTINCT vtu.view_name)
  INTO leftovers
  FROM information_schema.view_table_usage vtu
  WHERE vtu.view_schema='public'
    AND vtu.table_name IN ('vw_fish_overview_with_label','vw_fish_standard','vw_plasmids_overview');

  IF leftovers IS NOT NULL THEN
    RAISE EXCEPTION 'Cannot drop vw_*; still referenced by: %', leftovers;
  END IF;
END$$;

DROP VIEW IF EXISTS public.vw_fish_overview_with_label;
DROP VIEW IF EXISTS public.vw_fish_standard;
DROP VIEW IF EXISTS public.vw_plasmids_overview;

COMMIT;

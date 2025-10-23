BEGIN;

DO $$
DECLARE
  def text;
BEGIN
  IF to_regclass('public.v_fish_overview_with_label') IS NULL AND to_regclass('public.vw_fish_overview_with_label') IS NOT NULL THEN
    def := pg_get_viewdef('public.vw_fish_overview_with_label'::regclass, true);
    EXECUTE 'create or replace view public.v_fish_overview_with_label as ' || def;
  END IF;

  IF to_regclass('public.v_plasmids_overview') IS NULL AND to_regclass('public.vw_plasmids_overview') IS NOT NULL THEN
    def := pg_get_viewdef('public.vw_plasmids_overview'::regclass, true);
    EXECUTE 'create or replace view public.v_plasmids_overview as ' || def;
  END IF;

  IF to_regclass('public.v_fish_standard') IS NULL AND to_regclass('public.vw_fish_standard') IS NOT NULL THEN
    def := pg_get_viewdef('public.vw_fish_standard'::regclass, true);
    def := replace(def, 'public.vw_fish_overview_with_label', 'public.v_fish_overview_with_label');
    def := replace(def, 'vw_fish_overview_with_label', 'v_fish_overview_with_label');
    EXECUTE 'create or replace view public.v_fish_standard as ' || def;
  END IF;
END$$;

DO $$
DECLARE
  def text;
  def_new text;
BEGIN
  IF to_regclass('public.v_plasmids') IS NOT NULL THEN
    def := pg_get_viewdef('public.v_plasmids'::regclass, true);
    def_new := replace(def, 'public.vw_plasmids_overview', 'public.v_plasmids_overview');
    def_new := replace(def_new, 'vw_plasmids_overview', 'v_plasmids_overview');
    IF def_new IS DISTINCT FROM def THEN
      EXECUTE 'create or replace view public.v_plasmids as ' || def_new;
    END IF;
  END IF;
END$$;

DO $$
DECLARE
  leftovers text[];
BEGIN
  SELECT array_agg(distinct vtu.view_name)
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

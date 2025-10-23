BEGIN;

DO $$
DECLARE
  rec RECORD;
  def TEXT;
BEGIN
  CREATE TEMP TABLE _rename_map(old TEXT, new TEXT) ON COMMIT DROP;
  INSERT INTO _rename_map(old,new) VALUES
    ('vw_fish_overview_with_label','v_fish_overview_with_label'),
    ('vw_fish_standard','v_fish_standard'),
    ('vw_plasmids_overview','v_plasmids_overview');

  FOR rec IN
    SELECT v.schemaname, v.viewname, m.old, m.new
    FROM pg_views v
    CROSS JOIN _rename_map m
    WHERE v.schemaname = 'public'
      AND position(m.old in pg_get_viewdef((quote_ident(v.schemaname)||'.'||quote_ident(v.viewname))::regclass, true)) > 0
  LOOP
    def := pg_get_viewdef((quote_ident(rec.schemaname)||'.'||quote_ident(rec.viewname))::regclass, true);
    def := replace(def, rec.old, rec.new);
    EXECUTE 'create or replace view '
            || quote_ident(rec.schemaname) || '.' || quote_ident(rec.viewname)
            || ' as ' || def;
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

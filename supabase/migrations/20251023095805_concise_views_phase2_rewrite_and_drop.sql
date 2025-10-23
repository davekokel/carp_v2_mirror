BEGIN;

CREATE TEMP TABLE _map(old text, new text) ON COMMIT DROP;
INSERT INTO _map(old,new) VALUES
  ('v_fish_overview_final','v_fish'),
  ('v_fish_overview_with_label_final','v_tank_labels'),
  ('v_tanks_current_status_enriched','v_tanks'),
  ('v_tank_pairs_base','v_tank_pairs'),
  ('v_plasmids_overview_final','v_plasmids'),
  ('v_clutch_annotations_summary_enriched','v_clutch_annotations'),
  ('v_clutch_treatments_summary_enriched','v_clutch_treatments');

DO $$
DECLARE r record; def text; def_new text; m record;
BEGIN
  FOR r IN SELECT schemaname, viewname FROM pg_views WHERE schemaname='public' LOOP
    def := pg_get_viewdef((quote_ident(r.schemaname)||'.'||quote_ident(r.viewname))::regclass, true);
    def_new := def;
    FOR m IN SELECT * FROM _map LOOP
      def_new := replace(def_new, 'public.'||m.old, 'public.'||m.new);
      def_new := replace(def_new, m.old, m.new);
    END LOOP;
    IF def_new IS DISTINCT FROM def THEN
      EXECUTE 'CREATE OR REPLACE VIEW '||quote_ident(r.schemaname)||'.'||quote_ident(r.viewname)||' AS '||def_new;
    END IF;
  END LOOP;
END$$;

DO $$
DECLARE leftovers text[];
BEGIN
  SELECT array_agg(DISTINCT vtu.view_name)
  INTO leftovers
  FROM information_schema.view_table_usage vtu
  WHERE vtu.view_schema='public'
    AND vtu.table_name IN (SELECT old FROM _map);
  IF leftovers IS NOT NULL THEN
    RAISE EXCEPTION 'Cannot drop old names; still referenced by: %', leftovers;
  END IF;
END$$;

DROP VIEW IF EXISTS public.v_fish_overview_final;
DROP VIEW IF EXISTS public.v_fish_overview_with_label_final;
DROP VIEW IF EXISTS public.v_tanks_current_status_enriched;
DROP VIEW IF EXISTS public.v_tank_pairs_base;
DROP VIEW IF EXISTS public.v_plasmids_overview_final;
DROP VIEW IF EXISTS public.v_clutch_annotations_summary_enriched;
DROP VIEW IF EXISTS public.v_clutch_treatments_summary_enriched;

COMMIT;

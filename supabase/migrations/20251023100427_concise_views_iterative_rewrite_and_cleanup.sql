BEGIN;

CREATE TEMP TABLE _map(old text, new text) ON COMMIT DROP;
INSERT INTO _map(old,new) VALUES
  ('v_fish_overview_final','v_fish'),
  ('v_fish_overview_with_label_final','v_tank_labels'),
  ('v_fish_overview_with_label','v_tank_labels'),
  ('v_tanks_current_status_enriched','v_tanks'),
  ('v_tanks_current_status','v_tanks'),
  ('v_tank_pairs_base','v_tank_pairs'),
  ('v_plasmids_overview_final','v_plasmids'),
  ('v_plasmids_overview','v_plasmids'),
  ('v_clutch_annotations_summary_enriched','v_clutch_annotations'),
  ('v_clutch_annotations_summary','v_clutch_annotations'),
  ('v_clutch_treatments_summary_enriched','v_clutch_treatments'),
  ('v_clutch_treatments_summary','v_clutch_treatments'),
  ('v_fish_standard','v_fish'),
  ('v_fish_standard_clean_v2','v_fish');

-- Build candidate set: views whose current def still mentions any legacy token
CREATE TEMP TABLE _candidates(view_name text) ON COMMIT DROP;
INSERT INTO _candidates(view_name)
SELECT v.viewname
FROM pg_views v
WHERE v.schemaname='public'
  AND EXISTS (
    SELECT 1
    FROM _map m
    WHERE position(m.old in pg_get_viewdef((quote_ident(v.schemaname)||'.'||quote_ident(v.viewname))::regclass, true)) > 0
  );

-- Iterative rewrite: up to 6 passes
DO $$
DECLARE
  pass int := 1;
  changed int;
  r record;
  def text;
  def_new text;
  m record;
BEGIN
  LOOP
    changed := 0;

    FOR r IN
      SELECT view_name FROM _candidates
    LOOP
      BEGIN
        def := pg_get_viewdef(('public.'||quote_ident(r.view_name))::regclass, true);
        def_new := def;
        FOR m IN SELECT * FROM _map LOOP
          def_new := replace(def_new, 'public.'||m.old, 'public.'||m.new);
          def_new := replace(def_new, m.old, m.new);
        END LOOP;

        IF def_new IS DISTINCT FROM def THEN
          EXECUTE 'CREATE OR REPLACE VIEW public.'||quote_ident(r.view_name)||' AS '||def_new;
          changed := changed + 1;
        END IF;
      EXCEPTION
        WHEN others THEN
          -- dependency not ready yet; skip this view this pass
          CONTINUE;
      END;
    END LOOP;

    IF changed = 0 OR pass >= 6 THEN
      EXIT;
    END IF;

    pass := pass + 1;
  END LOOP;
END$$;

-- Try guarded drops for legacy names now unused
DO $$
DECLARE
  r record;
  cnt int;
BEGIN
  FOR r IN SELECT DISTINCT old FROM _map LOOP
    SELECT count(*) INTO cnt
    FROM information_schema.view_table_usage
    WHERE view_schema='public' AND table_name=r.old;
    IF cnt=0 THEN
      EXECUTE format('DROP VIEW IF EXISTS public.%I', r.old);
    END IF;
  END LOOP;
END$$;

COMMIT;

-- Report any stragglers still referencing legacy names
WITH legacy AS (SELECT DISTINCT old AS name FROM _map)
SELECT vtu.view_name AS dependent, vtu.table_name AS depends_on
FROM information_schema.view_table_usage vtu
JOIN legacy ON legacy.name = vtu.table_name
WHERE vtu.view_schema='public'
ORDER BY 1,2;

BEGIN;

DO $$
DECLARE src text;
BEGIN
  src := CASE
    WHEN to_regclass('public.v_fish_overview_final') IS NOT NULL THEN 'public.v_fish_overview_final'
    WHEN to_regclass('public.v_fish_standard') IS NOT NULL THEN 'public.v_fish_standard'
    WHEN to_regclass('public.v_fish_standard_clean_v2') IS NOT NULL THEN 'public.v_fish_standard_clean_v2'
    ELSE NULL END;
  IF src IS NULL THEN RAISE EXCEPTION 'No source view found for v_fish'; END IF;
  EXECUTE 'create or replace view public.v_fish as select * from '||src;
END$$;

DO $$
DECLARE src text;
BEGIN
  src := CASE
    WHEN to_regclass('public.v_fish_overview_with_label_final') IS NOT NULL THEN 'public.v_fish_overview_with_label_final'
    WHEN to_regclass('public.v_fish_overview_with_label') IS NOT NULL THEN 'public.v_fish_overview_with_label'
    ELSE NULL END;
  IF src IS NULL THEN RAISE EXCEPTION 'No source view found for v_tank_labels'; END IF;
  EXECUTE 'create or replace view public.v_tank_labels as select * from '||src;
END$$;

DO $$
DECLARE src text;
BEGIN
  src := CASE
    WHEN to_regclass('public.v_clutch_annotations_summary_enriched') IS NOT NULL THEN 'public.v_clutch_annotations_summary_enriched'
    WHEN to_regclass('public.v_clutch_annotations_summary') IS NOT NULL THEN 'public.v_clutch_annotations_summary'
    ELSE NULL END;
  IF src IS NULL THEN RAISE EXCEPTION 'No source view found for v_clutch_annotations'; END IF;
  EXECUTE 'create or replace view public.v_clutch_annotations as select * from '||src;
END$$;

DO $$
DECLARE src text;
BEGIN
  src := CASE
    WHEN to_regclass('public.v_clutch_treatments_summary_enriched') IS NOT NULL THEN 'public.v_clutch_treatments_summary_enriched'
    WHEN to_regclass('public.v_clutch_treatments_summary') IS NOT NULL THEN 'public.v_clutch_treatments_summary'
    ELSE NULL END;
  IF src IS NULL THEN RAISE EXCEPTION 'No source view found for v_clutch_treatments'; END IF;
  EXECUTE 'create or replace view public.v_clutch_treatments as select * from '||src;
END$$;

COMMIT;

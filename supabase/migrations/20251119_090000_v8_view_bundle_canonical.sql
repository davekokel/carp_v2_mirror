BEGIN;

-- v8 canonical view whitelist:
--   v_fish_overview
--   v_tanks
--   v_clutches_overview
--   v_imaging_clutches_rois
--   v_clutch_fluors_overview
--   v_treatments_overview
--   v_fluor_sources
--   v_genotype_transgene_alleles

DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT schemaname, viewname
    FROM pg_views
    WHERE schemaname = 'public'
      AND viewname LIKE 'v\_%'
      AND viewname NOT IN (
        'v_fish_overview',
        'v_tanks',
        'v_clutches_overview',
        'v_imaging_clutches_rois',
        'v_clutch_fluors_overview',
        'v_treatments_overview',
        'v_fluor_sources',
        'v_genotype_transgene_alleles'
      )
  LOOP
    RAISE NOTICE 'Dropping deprecated view %.% ', r.schemaname, r.viewname;
    EXECUTE format('DROP VIEW IF EXISTS %I.%I CASCADE;', r.schemaname, r.viewname);
  END LOOP;
END $$;

COMMIT;

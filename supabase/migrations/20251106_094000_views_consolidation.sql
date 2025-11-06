BEGIN;

-- 1) Drop obvious legacy views (if present)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname='public' AND viewname='v_plasmids_overview_v3') THEN
    EXECUTE 'DROP VIEW public.v_plasmids_overview_v3';
  END IF;

  IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname='public' AND viewname='v_clutch_instances_v3') THEN
    EXECUTE 'DROP VIEW public.v_clutch_instances_v3';
  END IF;

  IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname='public' AND viewname='v_clutch_instances_clean_compat') THEN
    EXECUTE 'DROP VIEW public.v_clutch_instances_clean_compat';
  END IF;

  IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname='public' AND viewname='v_clutch_instances_resolved_compat') THEN
    EXECUTE 'DROP VIEW public.v_clutch_instances_resolved_compat';
  END IF;
END$$;

-- Optional: if you’ve fully moved off the *_base stack, drop them.
-- Otherwise, leave them or rewrite them to point at the current v_clutch_instances.
-- DO $$ BEGIN
--   IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname='public' AND viewname='v_clutch_instances_base') THEN
--     EXECUTE 'DROP VIEW public.v_clutch_instances_base';
--   END IF;
--   IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname='public' AND viewname='v_clutch_instances_base_resolved') THEN
--     EXECUTE 'DROP VIEW public.v_clutch_instances_base_resolved';
--   END IF;
--   IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname='public' AND viewname='v_clutch_instances_clean') THEN
--     EXECUTE 'DROP VIEW public.v_clutch_instances_clean';
--   END IF;
-- END$$;

-- 2) Rewrite v_fish and v_fish_rich as thin wrappers over the canonical PK view

-- v_fish: minimal surface others might expect
DROP VIEW IF EXISTS public.v_fish;
CREATE VIEW public.v_fish AS
SELECT
  fish_code,
  nickname,
  birthday,
  genetic_background,
  line_building_stage,
  allele_count,
  genotype_rollup,
  fusion_rollup,
  fluor_rollup,
  tag_rollup,
  dye_rollup,
  created_at
FROM public.v_fish_overview_id;

COMMENT ON VIEW public.v_fish IS
'Wrapper over v_fish_overview_id (PK-based). Prefer v_fish_overview_id for full columns.';

-- v_fish_rich: richer set mapped from overview
DROP VIEW IF EXISTS public.v_fish_rich;
CREATE VIEW public.v_fish_rich AS
SELECT
  fish_code,
  nickname,
  birthday,
  genetic_background,
  line_building_stage,
  allele_count,
  allele_codes,
  allele_nicknames,
  transgenes,
  genotype_rollup,
  fusion_rollup,
  fluor_rollup,
  tag_rollup,
  dye_rollup,
  created_at
FROM public.v_fish_overview_id;

COMMENT ON VIEW public.v_fish_rich IS
'Wrapper over v_fish_overview_id (PK-based rollups). Kept for back-compat.';

-- 3) Warn in-database which views are canonical
COMMENT ON VIEW public.v_fish_overview_id IS
'CANON: Fish overview by primary keys; joins genotype and fluorescent marker rollups.';
COMMENT ON VIEW public.v_plasmids_rich IS
'CANON: Plasmid overview by primary keys; includes fusion_names_pretty (fluor::tag).';
COMMENT ON VIEW public.v_fish_fluorescent_markers IS
'Fluorescent treatment markers per fish; used by pages and loaders.';

COMMIT;

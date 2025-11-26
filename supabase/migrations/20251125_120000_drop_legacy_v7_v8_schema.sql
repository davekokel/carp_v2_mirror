BEGIN;

-- ─────────────────────────────────────────
-- 1. Drop legacy views that depend on old tables
-- ─────────────────────────────────────────

DROP VIEW IF EXISTS public.v_plasmids_overview CASCADE;
DROP VIEW IF EXISTS public.v_transgenes_overview CASCADE;
DROP VIEW IF EXISTS public.v_transgene_alleles_overview CASCADE;
DROP VIEW IF EXISTS public.v_fusions_overview CASCADE;
DROP VIEW IF EXISTS public.v_fish_overview CASCADE;
DROP VIEW IF EXISTS public.v_dyes_overview CASCADE;
DROP VIEW IF EXISTS public.v_tanks_overview CASCADE;
DROP VIEW IF EXISTS public.v_clutches_overview CASCADE;
DROP VIEW IF EXISTS public.v_roi_overview CASCADE;
DROP VIEW IF EXISTS public.v_fluor_sources CASCADE;

-- ─────────────────────────────────────────
-- 2. Drop genotype / fish-genotype legacy path
-- ─────────────────────────────────────────

DROP TABLE IF EXISTS public.genotype_fluors CASCADE;
DROP TABLE IF EXISTS public.genotype_fusions CASCADE;
DROP TABLE IF EXISTS public.genotype_transgene_alleles CASCADE;
DROP TABLE IF EXISTS public.genotypes CASCADE;
DROP TABLE IF EXISTS public.join_fish_transgene_alleles CASCADE;

-- ─────────────────────────────────────────
-- 3. Drop old treatment join tables
--    (v10 uses treatments + treatment_mixes + treatment_mix_* instead)
-- ─────────────────────────────────────────

DROP TABLE IF EXISTS public.join_treatment_plasmids CASCADE;
DROP TABLE IF EXISTS public.join_treatment_rnas CASCADE;
DROP TABLE IF EXISTS public.join_treatment_dyes CASCADE;
DROP TABLE IF EXISTS public.join_treatment_crisprs CASCADE;
DROP TABLE IF EXISTS public.treatment_fluors CASCADE;

-- ─────────────────────────────────────────
-- 4. Drop legacy construct tables
-- ─────────────────────────────────────────

DROP TABLE IF EXISTS public.plasmids_legacy CASCADE;
DROP TABLE IF EXISTS public.rnas_legacy CASCADE;
DROP TABLE IF EXISTS public.crisprs_legacy CASCADE;
DROP TABLE IF EXISTS public.join_plasmid_fusions_legacy CASCADE;
DROP TABLE IF EXISTS public.join_rna_fusions_legacy CASCADE;

-- Note: we KEEP constructs / construct_plasmids / construct_aliases /
--       fluors / tags / fusions / construct_fusions (the v10 world).

-- ─────────────────────────────────────────
-- 5. Drop unused fish grouping table
-- ─────────────────────────────────────────

DROP TABLE IF EXISTS public.fish_group CASCADE;

COMMIT;

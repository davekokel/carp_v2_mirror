BEGIN;

-- ─────────────────────────────────────────
-- 1. Drop legacy views that depended on old tables
--    (all have v10 replacements or are unused)
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

-- v10 views (v10_fish_lines_overview, v10_fish_instances_overview,
-- v10_line_fluors, v10_treatment_mix_fluors, v_imaging_clutches_rois, etc.)
-- are left untouched.

-- ─────────────────────────────────────────
-- 2. Drop genotype / fish-genotype legacy path
--    v10 uses fish_lines + join_line_alleles instead.
-- ─────────────────────────────────────────

DROP TABLE IF EXISTS public.genotype_fluors CASCADE;
DROP TABLE IF EXISTS public.genotype_fusions CASCADE;
DROP TABLE IF EXISTS public.genotype_transgene_alleles CASCADE;
DROP TABLE IF EXISTS public.genotypes CASCADE;
DROP TABLE IF EXISTS public.join_fish_transgene_alleles CASCADE;

-- ─────────────────────────────────────────
-- 3. Drop old treatment join tables
--    v10 uses treatments + treatment_mixes + treatment_mix_*.
-- ─────────────────────────────────────────

DROP TABLE IF EXISTS public.join_treatment_plasmids CASCADE;
DROP TABLE IF EXISTS public.join_treatment_rnas CASCADE;
DROP TABLE IF EXISTS public.join_treatment_dyes CASCADE;
DROP TABLE IF EXISTS public.join_treatment_crisprs CASCADE;
DROP TABLE IF EXISTS public.treatment_fluors CASCADE;

-- ─────────────────────────────────────────
-- 4. Drop legacy construct tables
--    v10 uses constructs / construct_plasmids / construct_aliases / construct_fusions.
-- ─────────────────────────────────────────

DROP TABLE IF EXISTS public.plasmids_legacy CASCADE;
DROP TABLE IF EXISTS public.rnas_legacy CASCADE;
DROP TABLE IF EXISTS public.crisprs_legacy CASCADE;
DROP TABLE IF EXISTS public.join_plasmid_fusions_legacy CASCADE;
DROP TABLE IF EXISTS public.join_rna_fusions_legacy CASCADE;

-- ─────────────────────────────────────────
-- 5. Drop unused fish grouping table
--    v10 uses fish_lines + fish_instances_v10 instead.
-- ─────────────────────────────────────────

DROP TABLE IF EXISTS public.fish_group CASCADE;

-- ─────────────────────────────────────────
-- 6. Drop old imaging ROI tables
--    v10 uses imaging_plates / imaging_slots / imaging_roi_annotations.
-- ─────────────────────────────────────────

DROP TABLE IF EXISTS public.imaging_rois CASCADE;
DROP TABLE IF EXISTS public.imaging_roi_files CASCADE;

-- ─────────────────────────────────────────
-- 7. Ensure v10 foreign keys for treatments/mixes are correct
-- ─────────────────────────────────────────

-- 7a) treatment_mix_constructs.mix_id → treatment_mixes(id)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_type = 'FOREIGN KEY'
      AND table_schema    = 'public'
      AND table_name      = 'treatment_mix_constructs'
      AND constraint_name = 'fk_tmc_mix'
  ) THEN
    ALTER TABLE public.treatment_mix_constructs
      ADD CONSTRAINT fk_tmc_mix
      FOREIGN KEY (mix_id)
      REFERENCES public.treatment_mixes(id)
      ON DELETE CASCADE;
  END IF;
END $$;

-- 7b) treatment_mix_constructs.construct_id → constructs(id)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_type = 'FOREIGN KEY'
      AND table_schema    = 'public'
      AND table_name      = 'treatment_mix_constructs'
      AND constraint_name = 'fk_tmc_construct'
  ) THEN
    ALTER TABLE public.treatment_mix_constructs
      ADD CONSTRAINT fk_tmc_construct
      FOREIGN KEY (construct_id)
      REFERENCES public.constructs(id)
      ON DELETE RESTRICT;
  END IF;
END $$;

-- 7c) treatment_mix_dyes.mix_id → treatment_mixes(id)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_type = 'FOREIGN KEY'
      AND table_schema    = 'public'
      AND table_name      = 'treatment_mix_dyes'
      AND constraint_name = 'fk_tmd_mix'
  ) THEN
    ALTER TABLE public.treatment_mix_dyes
      ADD CONSTRAINT fk_tmd_mix
      FOREIGN KEY (mix_id)
      REFERENCES public.treatment_mixes(id)
      ON DELETE CASCADE;
  END IF;
END $$;

-- 7d) treatment_mix_dyes.dye_id → dyes(id)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_type = 'FOREIGN KEY'
      AND table_schema    = 'public'
      AND table_name      = 'treatment_mix_dyes'
      AND constraint_name = 'fk_tmd_dye'
  ) THEN
    ALTER TABLE public.treatment_mix_dyes
      ADD CONSTRAINT fk_tmd_dye
      FOREIGN KEY (dye_id)
      REFERENCES public.dyes(id)
      ON DELETE RESTRICT;
  END IF;
END $$;

COMMIT;

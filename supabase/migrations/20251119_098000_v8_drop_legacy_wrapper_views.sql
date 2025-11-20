BEGIN;

DROP VIEW IF EXISTS public.clutch_marker_fusions CASCADE;
DROP VIEW IF EXISTS public.join_fish_genotypes CASCADE;
DROP VIEW IF EXISTS public.join_genotype_transgene_alleles CASCADE;
DROP VIEW IF EXISTS public.tank_memberships CASCADE;
DROP VIEW IF EXISTS public.treatment_fusions CASCADE;

COMMIT;

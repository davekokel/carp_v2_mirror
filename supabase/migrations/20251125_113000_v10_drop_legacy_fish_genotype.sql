BEGIN;

-- Drop legacy views that sit on top of old fish/genotype tables
DROP VIEW IF EXISTS public.v_fish_overview CASCADE;
DROP VIEW IF EXISTS public.v_fish_rich CASCADE;
DROP VIEW IF EXISTS public.v_genotypes_overview CASCADE;
DROP VIEW IF EXISTS public.v_transgenes_overview CASCADE;

-- Drop legacy fish grouping table (no longer used now that we have fish_lines)
DROP TABLE IF EXISTS public.fish_group CASCADE;

-- Drop legacy per-fish genotype linkage
DROP TABLE IF EXISTS public.join_fish_transgene_alleles CASCADE;

-- Drop legacy genotype archetype tables
DROP TABLE IF EXISTS public.genotype_transgene_alleles CASCADE;
DROP TABLE IF EXISTS public.genotype_fluors CASCADE;
DROP TABLE IF EXISTS public.genotype_fusions CASCADE;
DROP TABLE IF EXISTS public.genotypes CASCADE;

-- Drop legacy fish_instance table itself
DROP TABLE IF EXISTS public.fish_instance CASCADE;

COMMIT;

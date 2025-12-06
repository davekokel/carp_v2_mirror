BEGIN;

DROP VIEW IF EXISTS public.v_transgenes_overview CASCADE;
DROP VIEW IF EXISTS public.v_transgenes_overview_legacy CASCADE;

DROP VIEW IF EXISTS public.v_transgene_alleles_overview CASCADE;
DROP VIEW IF EXISTS public.v_transgene_alleles_overview_legacy CASCADE;

DROP VIEW IF EXISTS public.v_fusions_overview CASCADE;
DROP VIEW IF EXISTS public.v_fusions_overview_legacy CASCADE;

DROP VIEW IF EXISTS public.v_dyes_overview CASCADE;
DROP VIEW IF EXISTS public.v_dyes_overview_legacy CASCADE;

COMMIT;

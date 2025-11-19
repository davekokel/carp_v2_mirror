BEGIN;

ALTER TABLE public.clutches
    ADD COLUMN IF NOT EXISTS genotype_cross_label   text;

ALTER TABLE public.clutches
    ADD COLUMN IF NOT EXISTS genotype_base_codes    text;

ALTER TABLE public.clutches
    ADD COLUMN IF NOT EXISTS genotype_allele_codes  text;

ALTER TABLE public.clutches
    ADD COLUMN IF NOT EXISTS genotype_pretty        text;

COMMIT;

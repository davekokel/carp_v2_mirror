BEGIN;
CREATE UNIQUE INDEX IF NOT EXISTS uq_fta_fish_base
ON public.fish_transgene_alleles (fish_id, transgene_base_code);
COMMIT;

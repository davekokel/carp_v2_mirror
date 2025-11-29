BEGIN;

-- 1. Create fish-specific genotype table
CREATE TABLE IF NOT EXISTS public.genotypes_v11_fish (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    genotype_code       text UNIQUE NOT NULL,           -- e.g. G-FISH-ABCDE12345
    genotype_pretty     text,                           -- Tg(PDQM-005)gu2 × Tg(...)
    genotype_basecodes  text,                           -- PDQM-005||PDQM-034
    created_at          timestamptz DEFAULT now()
);

COMMENT ON TABLE public.genotypes_v11_fish IS
    'Stable, canonical genotype definitions for individual fish instances (v11).';


-- 2. Add FK column to fish instances table (v10)
ALTER TABLE public.fish_instances_v10
ADD COLUMN IF NOT EXISTS genotype_v11_id uuid;

ALTER TABLE public.fish_instances_v10
ADD CONSTRAINT fish_instances_v11_genotype_fk
    FOREIGN KEY (genotype_v11_id)
    REFERENCES public.genotypes_v11_fish(id)
    ON UPDATE CASCADE
    ON DELETE SET NULL;


COMMIT;

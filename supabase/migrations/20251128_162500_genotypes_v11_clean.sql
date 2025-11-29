BEGIN;

-- 1. Create canonical genotype library table
CREATE TABLE IF NOT EXISTS public.genotypes_v11 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    genotype_code TEXT UNIQUE NOT NULL,
    genotype_pretty TEXT,
    genotype_basecodes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. Add FK reference to clutches
ALTER TABLE public.clutches
    ADD COLUMN IF NOT EXISTS genotype_v11_id UUID
        REFERENCES public.genotypes_v11(id);

-- 3. Drop old clutch star view
DROP VIEW IF EXISTS public.v11_clutch_star;

-- 4. Recreate v11_clutch_star (NO IMAGING JOINS)
CREATE VIEW public.v11_clutch_star AS
WITH tbase AS (
    SELECT
        c.id AS clutch_id,
        c.clutch_code,
        c.clutch_date,
        c.estimated_egg_count,
        c.genotype_base_codes,
        c.genotype_v11_id,
        (SELECT COUNT(*) FROM public.imaging_clutch_memberships m WHERE m.clutch_id = c.id) AS n_imaging_slots,
        (SELECT COUNT(*) FROM public.imaging_clutch_memberships m WHERE m.clutch_id = c.id) AS n_rois
    FROM public.clutches c
),
treats AS (
    SELECT
        c.clutch_code,
        string_agg(DISTINCT t.treat_code, '||' ORDER BY t.treat_code) AS treat_codes,
        string_agg(DISTINCT cb.base_code, '||' ORDER BY cb.base_code) AS treat_basecodes
    FROM public.clutches c
    LEFT JOIN public.join_clutch_treatments jct ON jct.clutch_id = c.id
    LEFT JOIN public.treatments t ON t.id = jct.treatment_id
    LEFT JOIN public.treatment_mixes tm ON tm.treatment_id = t.id
    LEFT JOIN public.treatment_mix_constructs tmc ON tmc.mix_id = tm.id
    LEFT JOIN public.constructs cb ON cb.id = tmc.construct_id
    GROUP BY c.clutch_code
)
SELECT
    b.clutch_id,
    b.clutch_code,
    b.clutch_date,
    b.estimated_egg_count,
    b.n_imaging_slots,
    b.n_rois,
    b.genotype_base_codes,
    g.genotype_code AS genotype_v11_code,
    g.genotype_pretty AS genotype_pretty,
    t.treat_codes,
    t.treat_basecodes
FROM tbase b
LEFT JOIN public.genotypes_v11 g ON g.id = b.genotype_v11_id
LEFT JOIN treats t ON t.clutch_code = b.clutch_code
ORDER BY clutch_code;

COMMIT;

BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_star;

CREATE VIEW public.v11_clutch_star AS
WITH tbase AS (
    SELECT
        c.id              AS clutch_id,
        c.clutch_code,
        c.clutch_date,
        c.estimated_egg_count,
        c.genotype_base_codes,
        c.genotype_v11_id,
        (
            SELECT count(*)::bigint
            FROM public.imaging_clutch_memberships m
            WHERE m.clutch_id = c.id
        ) AS n_imaging_slots,
        (
            SELECT count(*)::bigint
            FROM public.imaging_clutch_memberships m
            WHERE m.clutch_id = c.id
        ) AS n_rois
    FROM public.clutches c
    WHERE
        c.source_system = 'legacy_imaging'
        OR EXISTS (
            SELECT 1
            FROM public.imaging_clutch_memberships m
            WHERE m.clutch_id = c.id
        )
),
treats AS (
    SELECT
        c.id AS clutch_id,
        string_agg(DISTINCT t_1.treat_code, '||' ORDER BY t_1.treat_code) AS treat_codes,
        string_agg(DISTINCT cb.base_code,   '||' ORDER BY cb.base_code)   AS treat_basecodes
    FROM public.clutches c
    LEFT JOIN public.join_clutch_treatments jct ON jct.clutch_id = c.id
    LEFT JOIN public.treatments             t_1 ON t_1.id = jct.treatment_id
    LEFT JOIN public.treatment_mixes        tm  ON tm.treatment_id = t_1.id
    LEFT JOIN public.treatment_mix_constructs tmc ON tmc.mix_id = tm.id
    LEFT JOIN public.constructs             cb  ON cb.id = tmc.construct_id
    WHERE
        c.source_system = 'legacy_imaging'
        OR EXISTS (
            SELECT 1
            FROM public.imaging_clutch_memberships m
            WHERE m.clutch_id = c.id
        )
    GROUP BY c.id
)
SELECT
    b.clutch_id,
    b.clutch_code,
    b.clutch_date,
    b.estimated_egg_count,
    b.n_imaging_slots,
    b.n_rois,
    b.genotype_base_codes,
    g.genotype_code        AS genotype_v11_code,
    g.genotype_basecodes   AS genotype_v11_basecodes,
    g.genotype_pretty,
    t.treat_codes,
    t.treat_basecodes
FROM tbase b
LEFT JOIN public.genotypes_v11 g ON g.id = b.genotype_v11_id
LEFT JOIN treats t               ON t.clutch_id = b.clutch_id
ORDER BY b.clutch_code;

COMMIT;

BEGIN;

-- Early v11_clutch_star stub to keep rebuild happy.
-- Later migrations (e.g. 20251128_150500_v11_clutch_star_genotype_and_treat_codes.sql)
-- redefine this view with full genotype + treatment semantics.

DROP VIEW IF EXISTS public.v11_clutch_star;

CREATE VIEW public.v11_clutch_star AS
WITH tbase AS (
    SELECT
        c.id               AS clutch_id,
        c.clutch_code,
        c.clutch_date,
        c.estimated_egg_count,
        c.genotype_base_codes,
        (
          SELECT COUNT(DISTINCT m.slot_id)
          FROM public.imaging_clutch_memberships m
          WHERE m.clutch_id = c.id
        ) AS n_imaging_slots,
        (
          SELECT COUNT(*)
          FROM public.imaging_clutch_memberships m
          WHERE m.clutch_id = c.id
        ) AS n_rois
    FROM public.clutches c
    WHERE c.source_system = 'legacy_imaging'
)
SELECT
    b.clutch_id,
    b.clutch_code,
    b.clutch_date,
    b.estimated_egg_count,
    COALESCE(b.n_imaging_slots, 0) AS n_imaging_slots,
    COALESCE(b.n_rois, 0)          AS n_rois,
    b.genotype_base_codes,
    NULL::text AS genotype_v11_code,
    NULL::text AS genotype_pretty,
    NULL::text AS treat_codes,
    NULL::text AS treat_basecodes
FROM tbase b
ORDER BY b.clutch_code;

COMMIT;

BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_star;

CREATE VIEW public.v11_clutch_star AS
WITH base AS (
  SELECT
    c.id::text                AS clutch_id,
    c.clutch_code::text       AS clutch_code,
    c.clutch_date             AS clutch_date,
    c.estimated_egg_count     AS estimated_egg_count,
    COALESCE(c.genotype_base_codes,   '')::text AS genotype_base_codes,
    COALESCE(c.genotype_allele_codes, '')::text AS genotype_allele_codes,
    COALESCE(c.genotype_pretty,       c.genotype_base_codes)::text AS genotype_pretty
  FROM public.clutches c
),
rois AS (
  SELECT
    v.clutch_code::text                      AS clutch_code,
    COUNT(*)                                 AS n_rois,
    COUNT(DISTINCT v.plate_code || '::' || v.slot_label) AS n_imaging_slots
  FROM public.v_imaging_clutches_rois v
  GROUP BY v.clutch_code
),
treats AS (
  SELECT
    c.id::text AS clutch_id,
    string_agg(DISTINCT t.treat_code, '||' ORDER BY t.treat_code) AS treat_codes,
    string_agg(
      DISTINCT COALESCE(cons.base_code, ''),
      '||' ORDER BY COALESCE(cons.base_code, '')
    ) FILTER (WHERE cons.base_code IS NOT NULL AND cons.base_code <> '') AS treat_basecodes
  FROM public.clutches c
  JOIN public.join_clutch_treatments jct
    ON jct.clutch_id = c.id
  JOIN public.treatments t
    ON t.id = jct.treatment_id
  LEFT JOIN public.treatment_mixes tm
    ON tm.treatment_id = t.id
  LEFT JOIN public.treatment_mix_constructs tmc
    ON tmc.mix_id = tm.id
  LEFT JOIN public.constructs cons
    ON cons.id = tmc.construct_id
  GROUP BY c.id
)
SELECT
  b.clutch_id,
  b.clutch_code,
  b.clutch_date,
  b.estimated_egg_count,
  COALESCE(r.n_imaging_slots, 0)::int AS n_imaging_slots,
  COALESCE(r.n_rois,          0)::int AS n_rois,
  b.genotype_base_codes,
  b.genotype_allele_codes,
  b.genotype_pretty,
  COALESCE(tr.treat_codes,     '')::text AS treat_codes,
  COALESCE(tr.treat_basecodes, '')::text AS treat_basecodes,
  NULL::text AS treat_fluor_label,
  NULL::text AS treat_organelle_fluor
FROM base b
LEFT JOIN rois   r  ON r.clutch_code = b.clutch_code
LEFT JOIN treats tr ON tr.clutch_id  = b.clutch_id;

COMMIT;

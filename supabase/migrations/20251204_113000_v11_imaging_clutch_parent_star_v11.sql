BEGIN;

-- Rebuild v11_imaging_clutch_parent_star using the v11 imaging stack
-- and drop the legacy helper view v_imaging_clutches_rois.

DROP VIEW IF EXISTS public.v11_imaging_clutch_parent_star;

CREATE VIEW public.v11_imaging_clutch_parent_star AS
WITH membership_base AS (
  SELECT
    icm.id::text               AS membership_id,
    icm.slot_id::text          AS slot_id,
    icm.clutch_id::text        AS clutch_id,
    icm.treated_clutch_id::text AS treated_clutch_id,
    icm.role                   AS membership_role,
    icm.embryo_count,
    icm.mount_notes,
    icm.created_at             AS membership_created_at
  FROM public.imaging_clutch_memberships icm
),

clutch_base AS (
  SELECT
    mb.*,
    c.clutch_code,
    c.clutch_date,
    c.estimated_egg_count
  FROM membership_base mb
  JOIN public.clutches c
    ON c.id = mb.clutch_id::uuid
),

clutch_geno AS (
  SELECT
    cs.clutch_id::text              AS clutch_id,
    cs.genotype_v11_basecodes       AS clutch_genotype_basecodes,
    cs.genotype_pretty              AS clutch_genotype_pretty,
    cs.treat_codes,
    cs.treat_basecodes,
    cs.expected_genotype_basecodes
  FROM public.v11_clutch_star cs
),

parent_geno AS (
  SELECT
    cp.clutch_id::text              AS clutch_id,
    cp.mother_fish_code,
    cp.mother_genotype_basecodes,
    cp.mother_genotype_pretty,
    cp.father_fish_code,
    cp.father_genotype_basecodes,
    cp.father_genotype_pretty
  FROM public.v11_clutch_parent_genotypes cp
)

SELECT
  cb.clutch_code,
  cb.clutch_date,
  cb.estimated_egg_count,
  cb.membership_id,
  cb.membership_role,
  cb.embryo_count,
  cb.mount_notes,
  cb.membership_created_at,
  r.plate_code,
  r.slot_label,
  r.roi_code,
  r.roi_index_within_slot        AS roi_index,
  r.roi_path                     AS data_path,
  cg.clutch_genotype_basecodes,
  cg.clutch_genotype_pretty,
  cg.treat_codes,
  cg.treat_basecodes,
  cg.expected_genotype_basecodes,
  pg.mother_fish_code,
  pg.mother_genotype_basecodes,
  pg.mother_genotype_pretty,
  pg.father_fish_code,
  pg.father_genotype_basecodes,
  pg.father_genotype_pretty
FROM clutch_base cb
LEFT JOIN public.v_roi_overview r
  ON r.slot_id = cb.slot_id
LEFT JOIN clutch_geno cg
  ON cg.clutch_id = cb.clutch_id
LEFT JOIN parent_geno pg
  ON pg.clutch_id = cb.clutch_id
ORDER BY
  cb.clutch_date DESC NULLS LAST,
  cb.clutch_code,
  r.plate_code,
  r.slot_label,
  r.roi_index_within_slot;

-- Legacy helper view is no longer needed
DROP VIEW IF EXISTS public.v_imaging_clutches_rois;

COMMIT;

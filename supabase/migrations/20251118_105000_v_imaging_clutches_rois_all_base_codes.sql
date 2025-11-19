BEGIN;

DROP VIEW IF EXISTS public.v_imaging_clutches_rois;

CREATE VIEW public.v_imaging_clutches_rois AS
SELECT
    c.id                      AS clutch_id,
    c.clutch_code,
    c.clutch_date,
    c.estimated_egg_count,
    c.notes                   AS clutch_notes,

    -- clutch genotype
    c.genotype_cross_label,
    c.genotype_base_codes,
    c.genotype_allele_codes,
    c.genotype_pretty,

    -- normalized mount/slot info
    n.sheet_row_index,
    n.date_mount,
    n.mount_id,
    n.slot_index_global,
    n.plate_index,
    n.slot_index,
    n.experimental_plate_id,
    n.experimental_slot_id,
    n.data_location,

    -- treatment info at clutch level
    tr.treatment_id,
    tr.treat_code,
    tr.treat_text,
    tr.kind_code,
    tr.treatment_notes,
    tr.plasmid_base_codes    AS treatment_plasmid_base_codes,
    tr.rna_base_codes        AS treatment_rna_base_codes,
    tr.dye_base_codes        AS treatment_dye_base_codes,

    -- combined genetic base-code picture (genotype + treatment)
    TRIM(BOTH ',' FROM
        CONCAT(
            COALESCE(c.genotype_base_codes, ''),
            CASE WHEN c.genotype_base_codes IS NOT NULL
                 AND (tr.plasmid_base_codes IS NOT NULL
                      OR tr.rna_base_codes IS NOT NULL
                      OR tr.dye_base_codes IS NOT NULL)
                 THEN ',' ELSE '' END,
            COALESCE(tr.plasmid_base_codes, ''),
            CASE WHEN tr.plasmid_base_codes IS NOT NULL
                     AND tr.rna_base_codes IS NOT NULL
                 THEN ',' ELSE '' END,
            COALESCE(tr.rna_base_codes, ''),
            CASE WHEN (tr.plasmid_base_codes IS NOT NULL
                       OR tr.rna_base_codes IS NOT NULL)
                     AND tr.dye_base_codes IS NOT NULL
                 THEN ',' ELSE '' END,
            COALESCE(tr.dye_base_codes, '')
        )
    ) AS all_base_codes,

    -- ROI-level info
    r.id                      AS imaging_roi_id,
    r.slot_id,
    r.roi_index,
    r.roi_name,
    r.data_path,
    r.channel_info,
    r.notes                   AS roi_notes,
    r.created_at              AS roi_created_at

FROM public.clutches c
JOIN public.v_imaging_clutch_memberships_norm n
  ON n.clutch_id = c.id
LEFT JOIN public.v_imaging_clutches_treatments tr
  ON tr.clutch_id = c.id
LEFT JOIN public.v_roi_overview r
  ON n.data_location IS NOT NULL
 AND r.data_path IS NOT NULL
 AND r.data_path LIKE n.data_location || '%'

WHERE c.clutch_code LIKE 'IMG_CLT_%';

COMMIT;

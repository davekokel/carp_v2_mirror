BEGIN;

DROP VIEW IF EXISTS public.v_imaging_mem_histone_rois;

CREATE VIEW public.v_imaging_mem_histone_rois AS
SELECT
    c.id                      AS clutch_id,
    c.clutch_code,
    c.clutch_date,
    c.estimated_egg_count,
    c.notes                   AS clutch_notes,

    -- genotype info
    c.genotype_cross_label,
    c.genotype_base_codes,
    c.genotype_allele_codes,
    c.genotype_pretty,

    -- treatment + marker info at clutch level
    tr.treatment_id,
    tr.treat_code,
    tr.treat_text,
    tr.kind_code,
    tr.treatment_notes,
    tr.plasmid_base_codes     AS treatment_plasmid_base_codes,
    tr.rna_base_codes         AS treatment_rna_base_codes,
    tr.dye_base_codes         AS treatment_dye_base_codes,
    tr.marker_fluor_codes     AS treatment_marker_fluor_codes,
    tr.marker_tag_codes       AS treatment_marker_tag_codes,

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

    -- membership (we treat each membership row as a "ROI-like" record)
    m.id                      AS membership_id,
    m.sheet_row_index,
    m.date_born,
    m.zf_female_genotype_text,
    m.zf_male_genotype_text,
    m.date_mount,
    m.mount_id,
    m.data_location           AS data_path,

    -- simple roi_index (1 per membership row, we can refine later)
    1                         AS roi_index,
    -- derive a roi_name from the tail of the path
    regexp_replace(
        regexp_replace(m.data_location, '\\\\', '/', 'g'),
        '^.*/',
        ''
    )                         AS roi_name

FROM public.clutches c
JOIN public.imaging_clutch_memberships m
  ON m.clutch_id = c.id
LEFT JOIN public.v_imaging_clutches_treatments tr
  ON tr.clutch_id = c.id
WHERE c.clutch_code LIKE 'IMG_CLT_%';

COMMIT;

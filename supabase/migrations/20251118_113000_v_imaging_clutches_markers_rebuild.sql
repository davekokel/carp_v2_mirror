BEGIN;

-- Drop dependent views in dependency order
DROP VIEW IF EXISTS public.v_imaging_clutches_rois;
DROP VIEW IF EXISTS public.v_imaging_clutches_treatments;

-- 1) Clutch-level treatments + marker rollups
CREATE VIEW public.v_imaging_clutches_treatments AS
SELECT
    c.id                      AS clutch_id,
    t.id                      AS treatment_id,
    t.treat_code,
    t.kind_code,
    t.treat_text,
    t.notes                   AS treatment_notes,
    COALESCE(
        string_agg(DISTINCT p.plasmid_base_code, ',' ORDER BY p.plasmid_base_code),
        ''
    ) AS plasmid_base_codes,
    COALESCE(
        string_agg(DISTINCT rna.rna_base_code, ',' ORDER BY rna.rna_base_code),
        ''
    ) AS rna_base_codes,
    COALESCE(
        string_agg(DISTINCT d.dye_base_code, ',' ORDER BY d.dye_base_code),
        ''
    ) AS dye_base_codes,
    tm.fluor_codes            AS marker_fluor_codes,
    tm.fluor_names            AS marker_fluor_names,
    tm.tag_codes              AS marker_tag_codes,
    tm.tag_names              AS marker_tag_names

FROM public.clutches c
JOIN public.join_clutch_treatments jct
  ON jct.clutch_id = c.id
JOIN public.treatments t
  ON t.id = jct.treatment_id

LEFT JOIN public.join_treatment_plasmids jtp
  ON jtp.treatment_id = t.id
LEFT JOIN public.plasmids p
  ON p.id = jtp.plasmid_id

LEFT JOIN public.join_treatment_rnas jtr
  ON jtr.treatment_id = t.id
LEFT JOIN public.rnas rna
  ON rna.id = jtr.rna_id

LEFT JOIN public.join_treatment_dyes jtd
  ON jtd.treatment_id = t.id
LEFT JOIN public.dyes d
  ON d.id = jtd.dye_id

LEFT JOIN public.v_imaging_treatments_markers tm
  ON tm.treatment_id = t.id

WHERE c.clutch_code LIKE 'IMG_CLT_%'
GROUP BY
    c.id,
    t.id,
    t.treat_code,
    t.kind_code,
    t.treat_text,
    t.notes,
    tm.fluor_codes,
    tm.fluor_names,
    tm.tag_codes,
    tm.tag_names;

-- 2) Full chain: clutch → mount/slot → treatments+markers → ROIs
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

    -- treatment + marker info at clutch level
    tr.treatment_id,
    tr.treat_code,
    tr.treat_text,
    tr.kind_code,
    tr.treatment_notes,
    tr.plasmid_base_codes      AS treatment_plasmid_base_codes,
    tr.rna_base_codes          AS treatment_rna_base_codes,
    tr.dye_base_codes          AS treatment_dye_base_codes,
    tr.marker_fluor_codes      AS treatment_marker_fluor_codes,
    tr.marker_fluor_names      AS treatment_marker_fluor_names,
    tr.marker_tag_codes        AS treatment_marker_tag_codes,
    tr.marker_tag_names        AS treatment_marker_tag_names,

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

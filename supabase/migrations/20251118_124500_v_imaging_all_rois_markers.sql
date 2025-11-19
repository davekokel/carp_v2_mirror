BEGIN;

DROP VIEW IF EXISTS public.v_imaging_all_rois_markers;

CREATE VIEW public.v_imaging_all_rois_markers AS
-- 1) Mem-histone imaging rows (one per imaging_sheet row)
SELECT
    'mem_histone'::text      AS dataset_source,

    m.clutch_id,
    m.clutch_code,
    m.clutch_date,
    m.estimated_egg_count,
    m.clutch_notes,

    m.genotype_cross_label,
    m.genotype_base_codes,
    m.genotype_allele_codes,
    m.genotype_pretty,
    m.genotype_marker_fluor_codes,
    m.genotype_marker_tag_codes,

    m.treatment_id,
    m.treat_code,
    m.treat_text,
    m.kind_code,
    m.treatment_notes,
    m.treatment_plasmid_base_codes,
    m.treatment_rna_base_codes,
    m.treatment_dye_base_codes,
    m.treatment_marker_fluor_codes,
    m.treatment_marker_tag_codes,

    m.all_marker_fluor_codes,
    m.all_base_codes,

    m.sheet_row_index,
    m.date_born,
    m.zf_female_genotype_text,
    m.zf_male_genotype_text,
    m.date_mount,
    m.mount_id,

    NULL::text               AS experimental_plate_id,
    NULL::text               AS experimental_slot_id,
    NULL::text               AS data_location,

    m.data_path,
    m.roi_index,
    m.roi_name,

    NULL::uuid               AS imaging_roi_id,
    NULL::uuid               AS slot_id,
    NULL::jsonb              AS channel_info,
    NULL::text               AS roi_notes,
    NULL::timestamptz        AS roi_created_at

FROM public.v_imaging_mem_histone_rois m

UNION ALL

-- 2) Cluster-linked ROIs (from v_imaging_clutches_rois_inherited)
SELECT
    'cluster_linked'::text   AS dataset_source,

    r.clutch_id,
    r.clutch_code,
    r.clutch_date,
    r.estimated_egg_count,
    r.clutch_notes,

    r.genotype_cross_label,
    r.genotype_base_codes,
    r.genotype_allele_codes,
    r.genotype_pretty,
    NULL::text               AS genotype_marker_fluor_codes,
    NULL::text               AS genotype_marker_tag_codes,

    r.treatment_id,
    r.treat_code,
    r.treat_text,
    r.kind_code,
    r.treatment_notes,
    r.treatment_plasmid_base_codes,
    r.treatment_rna_base_codes,
    r.treatment_dye_base_codes,
    r.treatment_marker_fluor_codes,
    r.treatment_marker_tag_codes,

    r.eff_treatment_marker_fluor_codes AS all_marker_fluor_codes,
    r.all_base_codes,

    r.sheet_row_index,
    NULL::date              AS date_born,
    NULL::text              AS zf_female_genotype_text,
    NULL::text              AS zf_male_genotype_text,
    r.date_mount,
    r.mount_id,

    r.experimental_plate_id,
    r.experimental_slot_id,
    r.data_location,

    r.data_path,
    r.roi_index,
    r.roi_name,

    r.imaging_roi_id,
    r.slot_id,
    r.channel_info,
    r.roi_notes,
    r.roi_created_at

FROM public.v_imaging_clutches_rois_inherited r;

COMMIT;

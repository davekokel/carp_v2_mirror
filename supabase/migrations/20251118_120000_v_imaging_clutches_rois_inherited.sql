BEGIN;

DROP VIEW IF EXISTS public.v_imaging_clutches_rois_inherited;

CREATE VIEW public.v_imaging_clutches_rois_inherited AS
WITH base AS (
    SELECT
        -- bring everything from the existing view
        c.*,
        NULLIF(c.treatment_marker_fluor_codes, '') AS tmf,
        NULLIF(c.treatment_marker_tag_codes, '')   AS tmt
    FROM public.v_imaging_clutches_rois c
),
inherit AS (
    SELECT
        b.*,
        COALESCE(
            b.tmf,
            MAX(b.tmf) OVER (PARTITION BY b.experimental_plate_id)
        ) AS eff_treatment_marker_fluor_codes,
        COALESCE(
            b.tmt,
            MAX(b.tmt) OVER (PARTITION BY b.experimental_plate_id)
        ) AS eff_treatment_marker_tag_codes
    FROM base b
)
SELECT
    -- everything from v_imaging_clutches_rois
    clutch_id,
    clutch_code,
    clutch_date,
    clutch_notes,
    estimated_egg_count,
    genotype_cross_label,
    genotype_base_codes,
    genotype_allele_codes,
    genotype_pretty,
    sheet_row_index,
    date_mount,
    mount_id,
    slot_index_global,
    plate_index,
    slot_index,
    experimental_plate_id,
    experimental_slot_id,
    data_location,
    treatment_id,
    treat_code,
    treat_text,
    kind_code,
    treatment_notes,
    treatment_plasmid_base_codes,
    treatment_rna_base_codes,
    treatment_dye_base_codes,
    treatment_marker_fluor_codes,
    treatment_marker_tag_codes,
    all_base_codes,
    imaging_roi_id,
    slot_id,
    roi_index,
    roi_name,
    data_path,
    channel_info,
    roi_notes,
    roi_created_at,

    -- new inherited/effective marker fields
    eff_treatment_marker_fluor_codes,
    eff_treatment_marker_tag_codes

FROM inherit;

COMMIT;

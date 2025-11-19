BEGIN;

DROP VIEW IF EXISTS public.v_imaging_all_rois_markers_complete;

CREATE VIEW public.v_imaging_all_rois_markers_complete AS
WITH base AS (
    SELECT *
    FROM public.v_imaging_all_rois_markers
)
SELECT
    -- provenance
    dataset_source,
    clutch_id,
    clutch_code,
    clutch_date,

    -- genotype (unchanged)
    genotype_cross_label,
    genotype_base_codes,
    genotype_allele_codes,
    genotype_pretty,
    genotype_marker_fluor_codes,
    genotype_marker_tag_codes,

    -- treatment (unchanged)
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

    all_marker_fluor_codes,
    all_base_codes,

    sheet_row_index,

    -- ⬇︎ birthday: real if available, else clutch_date
    COALESCE(date_born, clutch_date) AS birthday_filled,

    -- ⬇︎ parents: real if available, else explicit 'unknown'
    COALESCE(zf_female_genotype_text, 'unknown_female_parent') AS parent_female_filled,
    COALESCE(zf_male_genotype_text,   'unknown_male_parent')   AS parent_male_filled,

    date_mount,
    mount_id,

    -- ⬇︎ plate ID: real if available; else synth based on date_mount/clutch_date + mount_id
    COALESCE(
        experimental_plate_id,
        CASE
            WHEN date_mount IS NOT NULL THEN
                'SYN_' || to_char(date_mount, 'YYYYMMDD') || '_plate' || COALESCE(mount_id::text, '1')
            WHEN clutch_date IS NOT NULL THEN
                'SYN_' || to_char(clutch_date, 'YYYYMMDD') || '_plate' || COALESCE(mount_id::text, '1')
            ELSE
                'SYN_plate_unknown'
        END
    ) AS plate_id_filled,

    -- ⬇︎ slot ID: real if available; else synth plate_id + roi_index or 1
    COALESCE(
        experimental_slot_id,
        (
            COALESCE(
                experimental_plate_id,
                CASE
                    WHEN date_mount IS NOT NULL THEN
                        'SYN_' || to_char(date_mount, 'YYYYMMDD') || '_plate' || COALESCE(mount_id::text, '1')
                    WHEN clutch_date IS NOT NULL THEN
                        'SYN_' || to_char(clutch_date, 'YYYYMMDD') || '_plate' || COALESCE(mount_id::text, '1')
                    ELSE
                        'SYN_plate_unknown'
                END
            )
            || '-slot'
            || COALESCE(roi_index::text, '1')
        )
    ) AS slot_id_filled,

    -- ⬇︎ data_location: real if present; else parent folder of data_path; else 'unknown_location'
    COALESCE(
        data_location,
        CASE
            WHEN data_path IS NOT NULL THEN
                regexp_replace(
                    regexp_replace(data_path, '\\\\', '/', 'g'),
                    '/[^/]*$',
                    ''
                )
            ELSE
                NULL::text
        END,
        'unknown_location'
    ) AS data_location_filled,

    -- Keep ROI-level info as-is
    roi_index,
    roi_name,
    data_path,

    -- Pass through extra ROI fields in case you want them later
    imaging_roi_id,
    slot_id,
    channel_info,
    roi_notes,
    roi_created_at

FROM base;

COMMIT;

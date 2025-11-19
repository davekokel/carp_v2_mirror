BEGIN;

-- Drop inherited view first (depends on base)
DROP VIEW IF EXISTS public.v_imaging_clutches_rois_inherited;
DROP VIEW IF EXISTS public.v_imaging_clutches_rois;

-- Base view: clutch → membership → treatments → ROIs, with dataset-folder join
CREATE VIEW public.v_imaging_clutches_rois AS
WITH joined AS (
    SELECT
        c.id                      AS clutch_id,
        c.clutch_code,
        c.clutch_date,
        c.estimated_egg_count,
        c.notes                   AS clutch_notes,

        c.genotype_cross_label,
        c.genotype_base_codes,
        c.genotype_allele_codes,
        c.genotype_pretty,

        n.sheet_row_index,
        n.date_mount,
        n.mount_id,
        n.slot_index_global,
        n.plate_index,
        n.slot_index,
        n.experimental_plate_id,
        n.experimental_slot_id,
        n.data_location,

        tr.treatment_id,
        tr.treat_code,
        tr.treat_text,
        tr.kind_code,
        tr.treatment_notes,
        tr.plasmid_base_codes    AS treatment_plasmid_base_codes,
        tr.rna_base_codes        AS treatment_rna_base_codes,
        tr.dye_base_codes        AS treatment_dye_base_codes,
        tr.marker_fluor_codes    AS treatment_marker_fluor_codes,
        tr.marker_tag_codes      AS treatment_marker_tag_codes,

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
     AND
        -- normalize both to forward slashes
        LOWER(
          regexp_replace(
            -- parent folder of data_path, then last segment
            regexp_replace(
              regexp_replace(r.data_path, '\\\\', '/', 'g'),
              '/[^/]*$',
              ''
            ),
            '^.*/',
            ''
          )
        ) =
        LOWER(
          regexp_replace(
            regexp_replace(n.data_location, '\\\\', '/', 'g'),
            '^.*/',
            ''
          )
        )
    WHERE c.clutch_code LIKE 'IMG_CLT_%'
)
SELECT * FROM joined;

-- Inherited view: add eff_treatment_marker_* via plate-level inheritance
CREATE VIEW public.v_imaging_clutches_rois_inherited AS
WITH base AS (
    SELECT
        v.*,
        NULLIF(v.treatment_marker_fluor_codes, '') AS tmf,
        NULLIF(v.treatment_marker_tag_codes, '')   AS tmt
    FROM public.v_imaging_clutches_rois v
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
SELECT * FROM inherit;

COMMIT;

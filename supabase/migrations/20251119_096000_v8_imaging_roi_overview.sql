BEGIN;

-- v8: canonical ROI overview over imaging_roi_annotations

DROP VIEW IF EXISTS public.v_roi_overview;

CREATE VIEW public.v_roi_overview AS
SELECT
  -- Stable ID for UI: we use roi_code as the logical identifier
  r.roi_code                                 AS imaging_roi_id,
  r.roi_code                                 AS roi_code,
  r.plate_id_filled                          AS plate_code,
  r.slot_id_filled                           AS slot_label,
  r.fish                                     AS fish_code,
  r.roi_index_within_slot                    AS roi_index,
  r.roi_name,
  r.parent_female,
  r.parent_male,
  NULLIF(r.date_born, '')::date              AS birthday,
  NULL::text                                 AS genetic_background,
  r.genotype_pretty,
  r.genotype_base_codes,
  r.genotype_allele_codes,
  r.genotype_marker_fluor_codes,
  r.genotype_marker_tag_codes,
  r.treatment_plasmid_base_codes,
  r.treatment_rna_base_codes,
  r.treatment_marker_fluor_codes,
  r.treatment_marker_tag_codes,
  r.all_marker_fluor_codes,
  r.roi_dir                                  AS data_path,
  "Data location"                            AS data_location,
  r.slot_id                                  AS slot_id,
  "Date born"                                AS raw_date_born_text,
  "ZF female genotype"                       AS raw_zf_female_genotype,
  "ZF male genotype"                         AS raw_zf_male_genotype
FROM public.imaging_roi_annotations r;

COMMIT;

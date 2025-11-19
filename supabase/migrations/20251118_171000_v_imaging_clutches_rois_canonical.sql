BEGIN;

-- Replace any old v_imaging_clutches_rois
DROP VIEW IF EXISTS public.v_imaging_clutches_rois;

-- Canonical imaging chain: clutch -> mount/slot -> ROI (+ treatments).
-- This assumes:
--   - v_imaging_clutch_memberships_norm exists with clutch_id, sheet_row_index,
--     date_born, zf_female_genotype_text, zf_male_genotype_text, date_mount,
--     mount_id, slot_index_global, plate_index, slot_index,
--     experimental_plate_id, experimental_slot_id, data_location.
--   - v_imaging_clutches_treatments exists with clutch_id, treat_code, treat_text,
--     plasmid_base_codes, rna_base_codes, dye_base_codes, marker_fluor_codes, marker_tag_codes.
--   - v_roi_overview exists as defined in 20251118_170000_v_roi_overview_canonical.sql.

CREATE VIEW public.v_imaging_clutches_rois AS
WITH cm AS (
    SELECT
      n.clutch_id,
      c.clutch_code,
      c.clutch_date,
      n.sheet_row_index,
      n.date_born,
      n.zf_female_genotype_text,
      n.zf_male_genotype_text,
      n.date_mount,
      n.mount_id,
      n.slot_index_global,
      n.plate_index,
      n.slot_index,
      n.experimental_plate_id,
      n.experimental_slot_id,
      n.data_location
    FROM public.v_imaging_clutch_memberships_norm AS n
    JOIN public.clutches AS c
      ON c.id = n.clutch_id
),
ct AS (
    SELECT
      t.clutch_id,
      t.treat_code,
      t.treat_text,
      t.plasmid_base_codes    AS treatment_plasmid_base_codes,
      t.rna_base_codes        AS treatment_rna_base_codes,
      t.dye_base_codes        AS treatment_dye_base_codes,
      t.marker_fluor_codes    AS treatment_marker_fluor_codes,
      t.marker_tag_codes      AS treatment_marker_tag_codes
    FROM public.v_imaging_clutches_treatments AS t
)
SELECT
  cm.clutch_id,
  cm.clutch_code,
  cm.clutch_date,
  cm.date_born,
  cm.zf_female_genotype_text,
  cm.zf_male_genotype_text,
  cm.date_mount,
  cm.mount_id,
  cm.slot_index_global,
  cm.plate_index,
  cm.slot_index,
  cm.experimental_plate_id,
  cm.experimental_slot_id,
  cm.data_location,

  -- ROI / slot / plate / fish
  r.imaging_roi_id,
  r.roi_index,
  r.roi_name,
  r.roi_dir,
  r.data_path,
  r.plate_code,
  r.slot_label,
  r.fish_id,
  r.fish_code,
  r.fish_nickname,
  r.birthday,
  r.genetic_background,
  r.line_building_stage,

  -- Genotype placeholders (from v_roi_overview; currently NULL)
  r.genotype_code,
  r.genotype_name,
  r.genotype_base_codes,
  r.genotype_alleles_pretty,
  r.genotype_pretty,
  r.genotype_marker_fluors,
  r.genotype_marker_tags,

  -- Treatments / markers
  ct.treat_code,
  ct.treat_text,
  ct.treatment_plasmid_base_codes,
  ct.treatment_rna_base_codes,
  ct.treatment_dye_base_codes,
  ct.treatment_marker_fluor_codes,
  ct.treatment_marker_tag_codes

FROM cm
LEFT JOIN ct
  ON ct.clutch_id = cm.clutch_id
LEFT JOIN public.v_roi_overview AS r
  ON cm.data_location IS NOT NULL
 AND r.data_path IS NOT NULL
 -- crude but effective: match by normalized end-of-path segment
 AND (
       replace(cm.data_location, '\\', '/')
       = substring(r.data_path FROM '([^/]+/[^/]+)$')  -- match last two segments if you want
     OR r.data_path LIKE '%' || replace(cm.data_location, '\\', '/') || '%'
     );

COMMIT;

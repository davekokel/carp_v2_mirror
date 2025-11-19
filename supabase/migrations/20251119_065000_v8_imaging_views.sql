BEGIN;

----------------------------------------------------------------------
-- 1. v_roi_overview  (slot-based, synthetic ROI ID)
----------------------------------------------------------------------

DROP VIEW IF EXISTS public.v_roi_overview CASCADE;

CREATE VIEW public.v_roi_overview AS
SELECT
  (s.slot_label || '-roi' ||
    lpad(COALESCE(r.roi_index_within_slot, 1)::text, 2, '0')
  )                       AS imaging_roi_id,
  p.plate_code,
  s.slot_label,
  s.slot_index,
  r.roi_index_within_slot AS roi_index,
  r.roi_name,
  r.date_experiment,
  r.date_born            AS birthday,
  r.parent_female,
  r.parent_male,
  r.genotype_pretty,
  r.all_marker_fluor_codes,
  r.roi_dir              AS data_path
FROM public.imaging_roi_annotations r
JOIN public.imaging_slots s
  ON s.id = r.slot_id
JOIN public.imaging_plates p
  ON p.id = s.plate_id;

----------------------------------------------------------------------
-- 2. v_imaging_clutches_rois  (clutch → slot → ROI)
----------------------------------------------------------------------

DROP VIEW IF EXISTS public.v_imaging_clutches_rois CASCADE;

CREATE VIEW public.v_imaging_clutches_rois AS
SELECT
  c.id                      AS clutch_id,
  c.clutch_code,
  c.clutch_date,
  c.estimated_egg_count,
  c.source_system           AS clutch_source_system,
  c.import_batch_id         AS clutch_import_batch_id,

  m.id                      AS membership_id,
  m.embryo_count,
  m.mount_notes,

  p.plate_code,
  s.slot_label,
  s.slot_index,

  r.imaging_roi_id,
  r.roi_index,
  r.roi_name,
  r.birthday               AS roi_birthday,
  r.parent_female          AS roi_parent_female,
  r.parent_male            AS roi_parent_male,
  r.genotype_pretty,
  r.all_marker_fluor_codes,
  r.data_path
FROM public.clutches c
JOIN public.imaging_clutch_memberships m
  ON m.clutch_id = c.id
JOIN public.imaging_slots s
  ON s.id = m.slot_id
JOIN public.imaging_plates p
  ON p.id = s.plate_id
JOIN public.v_roi_overview r
  ON r.slot_label = s.slot_label;

----------------------------------------------------------------------
-- 3. v_crosses_overview  (fish + tanks + tank_pairs + crosses)
--    Use genotype *codes* only for now; genotypes table may not have pretties yet.
----------------------------------------------------------------------

DROP VIEW IF EXISTS public.v_crosses_overview CASCADE;

CREATE VIEW public.v_crosses_overview AS
SELECT
  cr.id                           AS cross_id,
  cr.cross_date,
  cr.expected_genotype_code,

  tp.id                           AS tank_pair_id,
  tp.tank_pair_code,
  mt.id                           AS mother_tank_id,
  mt.tank_code                    AS mother_tank_code,
  ft.id                           AS father_tank_id,
  ft.tank_code                    AS father_tank_code,

  ff.id                           AS female_fish_id,
  ff.fish_code                    AS female_fish_code,
  ff.nickname                     AS female_nickname,
  ff.standard_genotype_code       AS female_genotype_code,

  mf.id                           AS male_fish_id,
  mf.fish_code                    AS male_fish_code,
  mf.nickname                     AS male_nickname,
  mf.standard_genotype_code       AS male_genotype_code,

  cr.notes,
  cr.created_at
FROM public.crosses cr
LEFT JOIN public.tank_pairs tp
  ON tp.id = cr.tank_pair_id
LEFT JOIN public.tanks mt
  ON mt.id = tp.mother_tank_id
LEFT JOIN public.tanks ft
  ON ft.id = tp.father_tank_id
LEFT JOIN public.fish_instance ff
  ON ff.id = cr.female_fish_id
LEFT JOIN public.fish_instance mf
  ON mf.id = cr.male_fish_id;

----------------------------------------------------------------------
-- 4. v_clutches_overview  (crosses + clutches)
----------------------------------------------------------------------

DROP VIEW IF EXISTS public.v_clutches_overview CASCADE;

CREATE VIEW public.v_clutches_overview AS
SELECT
  cl.id                     AS clutch_id,
  cl.clutch_code,
  cl.clutch_date,
  cl.estimated_egg_count,
  cl.cross_id,
  cl.observed_genotype_code,
  cr.cross_date,
  cr.expected_genotype_code,
  ff.fish_code             AS female_fish_code,
  mf.fish_code             AS male_fish_code,
  cl.notes,
  cl.source_system,
  cl.import_batch_id,
  cl.created_at
FROM public.clutches cl
LEFT JOIN public.crosses cr
  ON cr.id = cl.cross_id
LEFT JOIN public.fish_instance ff
  ON ff.id = cr.female_fish_id
LEFT JOIN public.fish_instance mf
  ON mf.id = cr.male_fish_id;

----------------------------------------------------------------------
-- 5. v_clutch_fluors_overview  (clutch_fluor_markers + fluors)
----------------------------------------------------------------------

DROP VIEW IF EXISTS public.v_clutch_fluors_overview CASCADE;

CREATE VIEW public.v_clutch_fluors_overview AS
SELECT
  cl.id              AS clutch_id,
  cl.clutch_code,
  cl.clutch_date,
  cfm.fluor_id,
  f.fluor_code,
  f.fluor_name,
  f.excitation_nm,
  f.emission_nm,
  cfm.source,
  cfm.source_detail
FROM public.clutches cl
JOIN public.clutch_fluor_markers cfm
  ON cfm.clutch_id = cl.id
JOIN public.fluors f
  ON f.id = cfm.fluor_id;

COMMIT;

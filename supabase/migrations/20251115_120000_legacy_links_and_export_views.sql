BEGIN;

-- ---------------------------------------------------------------------------
-- Foreign keys for trusted legacy links (added NOT VALID for safety)
-- ---------------------------------------------------------------------------

-- legacy_clutches.legacy_pair_id -> legacy_pairs.id
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_legacy_clutches_pair'
      AND conrelid = 'public.legacy_clutches'::regclass
  ) THEN
    ALTER TABLE public.legacy_clutches
      ADD CONSTRAINT fk_legacy_clutches_pair
      FOREIGN KEY (legacy_pair_id)
      REFERENCES public.legacy_pairs(id)
      ON UPDATE CASCADE
      ON DELETE RESTRICT
      NOT VALID;
  END IF;
END$$;

-- imaging_rois.legacy_clutch_id -> legacy_clutches.id
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_imaging_rois_legacy_clutch'
      AND conrelid = 'public.imaging_rois'::regclass
  ) THEN
    ALTER TABLE public.imaging_rois
      ADD CONSTRAINT fk_imaging_rois_legacy_clutch
      FOREIGN KEY (legacy_clutch_id)
      REFERENCES public.legacy_clutches(id)
      ON UPDATE CASCADE
      ON DELETE SET NULL
      NOT VALID;
  END IF;
END$$;

-- imaging_rois.legacy_pair_id -> legacy_pairs.id
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_imaging_rois_legacy_pair'
      AND conrelid = 'public.imaging_rois'::regclass
  ) THEN
    ALTER TABLE public.imaging_rois
      ADD CONSTRAINT fk_imaging_rois_legacy_pair
      FOREIGN KEY (legacy_pair_id)
      REFERENCES public.legacy_pairs(id)
      ON UPDATE CASCADE
      ON DELETE SET NULL
      NOT VALID;
  END IF;
END$$;

-- imaging_rois.fish_id -> fish.id (core link, also NOT VALID to avoid surprises)
DO $$
BEGIN
  IF to_regclass('public.fish') IS NOT NULL
     AND NOT EXISTS (
       SELECT 1
       FROM pg_constraint
       WHERE conname = 'fk_imaging_rois_fish'
         AND conrelid = 'public.imaging_rois'::regclass
     )
  THEN
    ALTER TABLE public.imaging_rois
      ADD CONSTRAINT fk_imaging_rois_fish
      FOREIGN KEY (fish_id)
      REFERENCES public.fish(id)
      ON UPDATE CASCADE
      ON DELETE SET NULL
      NOT VALID;
  END IF;
END$$;

-- ---------------------------------------------------------------------------
-- Export views for legacy snapshot/re-import
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW public.export_legacy_pairs AS
SELECT
  lp.id                 AS legacy_pair_id,
  lp.dataset            AS dataset,
  lp.zf_female_genotype AS zf_female_genotype,
  lp.zf_male_genotype   AS zf_male_genotype,
  lp.pair_code          AS pair_code,
  lp.created_at         AS created_at
FROM public.legacy_pairs lp;

CREATE OR REPLACE VIEW public.export_legacy_clutches AS
SELECT
  lc.id             AS legacy_clutch_id,
  lc.legacy_pair_id AS legacy_pair_id,
  lc.dataset        AS dataset,
  lc.date_mount     AS date_mount,
  lc.clutch_code    AS clutch_code,
  lc.created_at     AS created_at
FROM public.legacy_clutches lc;

-- Only ROIs that are clearly tied to legacy (have a legacy pair or clutch)
CREATE OR REPLACE VIEW public.export_legacy_imaging_rois AS
SELECT
  ir.id                             AS imaging_roi_id,
  ir.fish_id                        AS fish_id,
  ir.fish_label                     AS fish_label,
  ir.roi_index                      AS roi_index,
  ir.roi_name                       AS roi_name,
  ir.roi_dir                        AS roi_dir,
  ir.dataset                        AS dataset,
  ir.experiment_name                AS experiment_name,
  ir.data_location                  AS data_location,
  ir.mount_row_index_scored         AS mount_row_index_scored,
  ir.mount_id                       AS mount_id,
  ir.date_experiment                AS date_experiment,
  ir.date_mount                     AS date_mount,
  ir.raw_id                         AS raw_id,
  ir.legacy_pair_id                 AS legacy_pair_id,
  ir.legacy_clutch_id               AS legacy_clutch_id,
  ir.zf_female_genotype             AS zf_female_genotype,
  ir.zf_male_genotype               AS zf_male_genotype,
  ir.additional_plasmids_injected   AS additional_plasmids_injected,
  ir.additional_mrnas_injected      AS additional_mrnas_injected,
  ir.additonal_proteins_injected    AS additonal_proteins_injected,
  ir.additonal_dye_and_chemicals    AS additonal_dye_and_chemicals,
  ir.date_born                      AS date_born,
  ir.time_mounted                   AS time_mounted,
  ir.mounting_orientation           AS mounting_orientation,
  ir.date_screened_initial_feedback AS date_screened_initial_feedback,
  ir.date_imaged                    AS date_imaged
FROM public.imaging_rois ir
WHERE ir.legacy_pair_id IS NOT NULL
   OR ir.legacy_clutch_id IS NOT NULL;

COMMIT;

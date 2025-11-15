BEGIN;

-- 1) Propagate timing fields within raw.imaging_rois_raw
WITH agg AS (
  SELECT
    dataset,
    fish_label,
    max(NULLIF(date_born, 'NaN'))                      AS date_born,
    max(NULLIF(time_mounted, 'NaN'))                   AS time_mounted,
    max(NULLIF(mounting_orientation, 'NaN'))           AS mounting_orientation,
    max(NULLIF(date_screened_initial_feedback, 'NaN')) AS date_screened_initial_feedback,
    max(NULLIF(date_imaged, 'NaN'))                    AS date_imaged
  FROM raw.imaging_rois_raw
  GROUP BY dataset, fish_label
)
UPDATE raw.imaging_rois_raw r
SET
  date_born                      = COALESCE(r.date_born,                      a.date_born),
  time_mounted                   = COALESCE(r.time_mounted,                   a.time_mounted),
  mounting_orientation           = COALESCE(r.mounting_orientation,           a.mounting_orientation),
  date_screened_initial_feedback = COALESCE(r.date_screened_initial_feedback, a.date_screened_initial_feedback),
  date_imaged                    = COALESCE(r.date_imaged,                    a.date_imaged)
FROM agg a
WHERE r.dataset    = a.dataset
  AND r.fish_label = a.fish_label;

-- 2) Sync public.imaging_rois from raw using raw_id
UPDATE public.imaging_rois ir
SET
  date_born                      = r.date_born,
  time_mounted                   = r.time_mounted,
  mounting_orientation           = r.mounting_orientation,
  date_screened_initial_feedback = r.date_screened_initial_feedback,
  date_imaged                    = r.date_imaged
FROM raw.imaging_rois_raw r
WHERE ir.raw_id = r.id;

COMMIT;

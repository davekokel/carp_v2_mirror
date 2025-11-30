BEGIN;

DROP VIEW IF EXISTS public.v11_imaging_roi_star CASCADE;

CREATE VIEW public.v11_imaging_roi_star AS
SELECT
    r.id                       AS roi_id,
    r.slot_id,
    r.roi_index_within_slot,
    r.roi_code,
    r.roi_path,
    r.roi_note_anatomy,
    r.created_at
FROM public.imaging_roi_annotations r;

COMMENT ON VIEW public.v11_imaging_roi_star IS
  'v11 ROI star: canonical metadata for each ROI with no fish/genotype joins (slot- and clutch-level integration happens upstream).';

COMMIT;

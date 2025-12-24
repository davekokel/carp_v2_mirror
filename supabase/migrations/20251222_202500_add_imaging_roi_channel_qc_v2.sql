BEGIN;

CREATE TABLE IF NOT EXISTS public.imaging_roi_channel_qc_v2 (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  roi_id uuid NOT NULL REFERENCES public.imaging_roi_annotations(id) ON DELETE CASCADE,
  roi_code text NOT NULL,
  roi_path text NOT NULL,

  cam text,
  channel text,
  wavelength_nm integer,

  keep boolean NOT NULL DEFAULT true,
  kill_reason text,
  source text,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS imaging_roi_channel_qc_v2_uniq
  ON public.imaging_roi_channel_qc_v2 (roi_id, cam, channel, wavelength_nm);

CREATE INDEX IF NOT EXISTS imaging_roi_channel_qc_v2_roi_id
  ON public.imaging_roi_channel_qc_v2 (roi_id);

CREATE INDEX IF NOT EXISTS imaging_roi_channel_qc_v2_roi_code
  ON public.imaging_roi_channel_qc_v2 (roi_code);

CREATE INDEX IF NOT EXISTS imaging_roi_channel_qc_v2_roi_path
  ON public.imaging_roi_channel_qc_v2 (roi_path);

CREATE OR REPLACE FUNCTION public.touch_updated_at_imaging_roi_channel_qc_v2()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_touch_imaging_roi_channel_qc_v2 ON public.imaging_roi_channel_qc_v2;

CREATE TRIGGER trg_touch_imaging_roi_channel_qc_v2
BEFORE UPDATE ON public.imaging_roi_channel_qc_v2
FOR EACH ROW
EXECUTE FUNCTION public.touch_updated_at_imaging_roi_channel_qc_v2();

CREATE OR REPLACE VIEW public.v_imaging_roi_channel_qc_rollup_v2 AS
SELECT
  roi_id,
  roi_code,
  COUNT(*) AS n_channels_total,
  SUM(CASE WHEN keep THEN 1 ELSE 0 END) AS n_channels_kept,
  STRING_AGG(
    DISTINCT concat_ws(':', cam, channel, CASE WHEN wavelength_nm IS NULL THEN NULL ELSE wavelength_nm::text END),
    '; ' ORDER BY concat_ws(':', cam, channel, CASE WHEN wavelength_nm IS NULL THEN NULL ELSE wavelength_nm::text END)
  ) FILTER (WHERE keep) AS kept_channels_key
FROM public.imaging_roi_channel_qc_v2
GROUP BY roi_id, roi_code;

COMMIT;

BEGIN;

CREATE OR REPLACE FUNCTION public.legacy_roi_path_key(p text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT
    CASE
      WHEN p IS NULL THEN NULL
      WHEN position('Aang_Foundation/' in p) > 0 THEN substring(p from position('Aang_Foundation/' in p))
      WHEN position('Korra_Foundation/' in p) > 0 THEN substring(p from position('Korra_Foundation/' in p))
      WHEN p LIKE 'Aang_Foundation/%' THEN p
      WHEN p LIKE 'Korra_Foundation/%' THEN p
      ELSE NULL
    END;
$$;

CREATE OR REPLACE VIEW public.v_legacy_roi_channels_v5_by_roi_id AS
SELECT
  r.roi_id,
  r.roi_path,
  c.channel_name,
  c.n_tiffs,
  c.decision_status,
  c.note
FROM public.v11_roi_flat_table_display r
JOIN public.legacy_roi_channels_v5 c
  ON public.legacy_roi_path_key(r.roi_path) = c.roi_path;

COMMIT;

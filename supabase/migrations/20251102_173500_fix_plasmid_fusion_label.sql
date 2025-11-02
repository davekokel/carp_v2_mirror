BEGIN;

-- Return a '; ' joined list of fusion labels for a plasmid code.
-- Order of preference:
--   1) Direct labels via join_plasmid_fusions → fusions.fusion_name
--   2) Fallback to v_plasmids_rich.fusion_names (if present)
-- Never fall back to plasmids.name/promoter.
CREATE OR REPLACE FUNCTION public.plasmid_fusion_label(p_code text)
RETURNS text
LANGUAGE sql
STABLE
AS $$
WITH direct AS (
  SELECT DISTINCT btrim(f.fusion_name) AS label
  FROM public.join_plasmid_fusions j
  JOIN public.fusions f ON f.fusion_code = j.fusion_code
  WHERE lower(j.plasmid_code) = lower(p_code)
),
rolled AS (
  SELECT NULLIF(btrim(v.fusion_names), '') AS label
  FROM public.v_plasmids_rich v
  WHERE lower(v.plasmid_code) = lower(p_code)
  LIMIT 1
)
SELECT COALESCE(
  (SELECT string_agg(label, '; ' ORDER BY label) FROM direct),
  (SELECT label FROM rolled)
);
$$;

COMMIT;

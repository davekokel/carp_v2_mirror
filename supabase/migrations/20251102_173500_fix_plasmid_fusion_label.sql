BEGIN;

CREATE OR REPLACE FUNCTION public.plasmid_fusion_label(plasmid_code text)
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT
    COALESCE(
      NULLIF(
        string_agg(DISTINCT f.fusion_name, ';' ORDER BY f.fusion_name),
        ''
      ),
      ''
    )
  FROM public.join_plasmid_fusions j
  JOIN public.fusions f
    ON f.fusion_code = j.fusion_code
  WHERE j.plasmid_code = $1
$$;

COMMIT;

BEGIN;

CREATE OR REPLACE FUNCTION public.ensure_ft_markers_from_transgene(p_ft_code text)
RETURNS void
LANGUAGE plpgsql
AS $fn$
BEGIN
  -- 1) Ensure TF master (FK prerequisite)
  INSERT INTO public.treatments_fluorescent (ft_code, ft_text, created_by)
  VALUES (p_ft_code, ''::text, 'system')
  ON CONFLICT (ft_code) DO NOTHING;

  -- 2) Derive and upsert FT markers from plasmid → fusion → (fluor, tag)
  INSERT INTO public.ft_proteins (ft_code, fluor_code, tag_code)
  SELECT DISTINCT
         p_ft_code AS ft_code,
         fl.fluor_code,
         tg.tag_code
  FROM public.plasmids p
  LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
  LEFT JOIN public.fusions f               ON f.id = jpf.fusion_id
  LEFT JOIN public.fluors  fl              ON fl.id = f.fluor_id
  LEFT JOIN public.tags    tg              ON tg.id = f.tag_id
  WHERE p.code = p_ft_code
    AND (fl.fluor_code IS NOT NULL OR tg.tag_code IS NOT NULL)
  ON CONFLICT (ft_code, fluor_code, tag_code) DO NOTHING;
END;
$fn$;

COMMIT;

BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='uq_ft_proteins_ft_tag_fluor'
  ) THEN
    EXECUTE '
      CREATE UNIQUE INDEX uq_ft_proteins_ft_tag_fluor
      ON public.ft_proteins(ft_code, COALESCE(tag_code,''∅''), fluor_code)
    ';
  END IF;
END$$;

CREATE OR REPLACE FUNCTION public.ensure_ft_markers_from_transgene(p_ft_code text)
RETURNS void
LANGUAGE plpgsql
AS $fn$
BEGIN
  INSERT INTO public.ft_proteins(ft_code, fluor_code, tag_code)
  SELECT DISTINCT p_ft_code.ft_code, fl.fluor_code, tg.tag_code
  FROM (
    SELECT p_ft_code.p_ft_code AS ft_code
  ) AS p_ft_code
  JOIN public.plasmids p
    ON p.code = p_ft_code.ft_code
  LEFT JOIN public.join_plasmid_fusions jpf
    ON jpf.plasmid_id = p.id
  LEFT JOIN public.fusions f
    ON f.id = jpf.fusion_id
  LEFT JOIN public.fluors fl
    ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg
    ON tg.id = f.tag_id
  WHERE fl.fluor_code IS NOT NULL OR tg.tag_code IS NOT NULL
  ON CONFLICT (ft_code, COALESCE(tag_code,'∅'), fluor_code) DO NOTHING;
END;
$fn$;

COMMIT;

BEGIN;

-- Resolve fluor by code, name, or alias (case-insensitive)
CREATE OR REPLACE FUNCTION public.resolve_fluor_id(_tok text)
RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT id FROM public.fluors
   WHERE lower(fluor_code)=lower(btrim(_tok))
      OR lower(COALESCE(fluor_name,''))=lower(btrim(_tok))
  UNION
  SELECT fa.fluor_id FROM public.fluor_aliases fa
   WHERE fa.alias_norm=lower(btrim(_tok))
  LIMIT 1;
$$;

-- Resolve tag by code, name, or alias (case-insensitive)
CREATE OR REPLACE FUNCTION public.resolve_tag_id(_tok text)
RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT id FROM public.tags
   WHERE lower(tag_code)=lower(btrim(_tok))
      OR lower(COALESCE(tag_name,''))=lower(btrim(_tok))
  UNION
  SELECT ta.tag_id FROM public.tag_aliases ta
   WHERE ta.alias_norm=lower(btrim(_tok))
  LIMIT 1;
$$;

COMMIT;

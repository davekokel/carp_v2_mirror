BEGIN;

CREATE OR REPLACE FUNCTION public.resolve_fluor_id(_tok text)
RETURNS uuid LANGUAGE sql STABLE AS $$
  WITH t AS (SELECT lower(btrim(_tok)) AS k)
  SELECT id FROM public.fluors f, t
   WHERE lower(f.fluor_code)=t.k OR lower(COALESCE(f.fluor_name,''))=t.k
  UNION
  SELECT target_id FROM public.join_aliases ja, t
   WHERE ja.target_kind='fluor'::alias_target_kind AND ja.alias_norm=t.k
  LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION public.resolve_tag_id(_tok text)
RETURNS uuid LANGUAGE sql STABLE AS $$
  WITH t AS (SELECT lower(btrim(_tok)) AS k)
  SELECT id FROM public.tags tg, t
   WHERE lower(tg.tag_code)=t.k OR lower(COALESCE(tg.tag_name,''))=t.k
  UNION
  SELECT target_id FROM public.join_aliases ja, t
   WHERE ja.target_kind='tag'::alias_target_kind AND ja.alias_norm=t.k
  LIMIT 1;
$$;

-- optional, if you want dye aliases later
CREATE OR REPLACE FUNCTION public.resolve_dye_id(_tok text)
RETURNS uuid LANGUAGE sql STABLE AS $$
  WITH t AS (SELECT lower(btrim(_tok)) AS k)
  SELECT id FROM public.dyes d, t
   WHERE lower(d.dye_code)=t.k OR lower(COALESCE(d.dye_name,''))=t.k
  UNION
  SELECT target_id FROM public.join_aliases ja, t
   WHERE ja.target_kind='dye'::alias_target_kind AND ja.alias_norm=t.k
  LIMIT 1;
$$;

COMMIT;

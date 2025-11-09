BEGIN;

-- 1) symbol map for case-insensitive resolution
CREATE OR REPLACE VIEW public.v_symbol_map AS
WITH flu AS (
  SELECT 'fluor'::text AS kind, lower(f.fluor_code) AS sym, f.id AS target_id FROM public.fluors f
  UNION ALL SELECT 'fluor', lower(COALESCE(f.fluor_name,'')), f.id FROM public.fluors f
  UNION ALL SELECT 'fluor', ja.alias_norm, ja.target_id
    FROM public.join_aliases ja WHERE ja.target_kind='fluor'::public.alias_target_kind
),
tg AS (
  SELECT 'tag'::text AS kind, lower(t.tag_code) AS sym, t.id AS target_id FROM public.tags t
  UNION ALL SELECT 'tag', lower(COALESCE(t.tag_name,'')), t.id FROM public.tags t
  UNION ALL SELECT 'tag', ja.alias_norm, ja.target_id
    FROM public.join_aliases ja WHERE ja.target_kind='tag'::public.alias_target_kind
)
SELECT * FROM flu
UNION ALL
SELECT * FROM tg;

-- 2) helper: resolve a symbol to id by kind
CREATE OR REPLACE FUNCTION public.resolve_symbol_id(_kind text, _sym text)
RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT target_id
  FROM public.v_symbol_map
  WHERE kind=_kind AND sym=lower(btrim(_sym))
  LIMIT 1
$$;

-- 3) canonical: ensure_fusion_id(fluor_sym, tag_sym, tag_pos_text) → fusion_id
CREATE OR REPLACE FUNCTION public.ensure_fusion_id(_fluor_sym text, _tag_sym text, _tag_pos text)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
  fid uuid;
  tid uuid;
  pos text;
  existing_id uuid;
BEGIN
  IF _fluor_sym IS NULL OR btrim(_fluor_sym)='' THEN
    RETURN NULL;
  END IF;

  fid := public.resolve_symbol_id('fluor', _fluor_sym);
  IF fid IS NULL THEN
    RETURN NULL;  -- unknown fluor
  END IF;

  IF _tag_sym IS NULL OR btrim(_tag_sym)='' THEN
    tid := NULL;
    pos := NULL;  -- fluor-only: ignore tag_pos
  ELSE
    tid := public.resolve_symbol_id('tag', _tag_sym);
    IF tid IS NULL THEN
      RETURN NULL;  -- unknown tag
    END IF;
    pos := CASE WHEN upper(btrim(COALESCE(_tag_pos,''))) IN ('N','C')
                THEN upper(btrim(_tag_pos))
                ELSE NULL
           END;
  END IF;

  -- first try to find exact match (including pos)
  SELECT id INTO existing_id
  FROM public.fusions
  WHERE fluor_id=fid
    AND ( (tid IS NULL AND tag_id IS NULL)
          OR (tag_id=tid AND (tag_pos IS NOT DISTINCT FROM pos)) )
  LIMIT 1;

  IF existing_id IS NOT NULL THEN
    RETURN existing_id;
  END IF;

  -- if tag present and there exists a sibling (fid, tid, ANY pos),
  -- try to backfill only if safe (i.e., no row with desired pos)
  IF tid IS NOT NULL THEN
    IF pos IS NOT NULL THEN
      -- safe backfill: move NULL/other to desired pos if no exact row exists
      UPDATE public.fusions f
      SET tag_pos = pos
      WHERE f.fluor_id=fid
        AND f.tag_id  =tid
        AND f.tag_pos IS DISTINCT FROM pos
        AND NOT EXISTS (
          SELECT 1 FROM public.fusions f2
          WHERE f2.fluor_id=fid AND f2.tag_id=tid AND (f2.tag_pos IS NOT DISTINCT FROM pos)
        )
      RETURNING id INTO existing_id;

      IF existing_id IS NOT NULL THEN
        RETURN existing_id;
      END IF;
    END IF;
  END IF;

  -- insert the exact desired row
  INSERT INTO public.fusions(fluor_id, tag_id, tag_pos)
  VALUES (fid, tid, pos)
  ON CONFLICT DO NOTHING;

  -- return the id (now must exist)
  SELECT id INTO existing_id
  FROM public.fusions
  WHERE fluor_id=fid
    AND ( (tid IS NULL AND tag_id IS NULL)
          OR (tag_id=tid AND (tag_pos IS NOT DISTINCT FROM pos)) )
  LIMIT 1;

  RETURN existing_id;
END
$$;

COMMIT;

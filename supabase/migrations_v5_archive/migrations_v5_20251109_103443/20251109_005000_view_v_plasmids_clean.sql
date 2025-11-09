BEGIN;

DROP VIEW IF EXISTS public.v_plasmids;

-- Modern v_plasmids: plasmids + rollups of associated fluors/tags via join_plasmid_fusions
CREATE VIEW public.v_plasmids AS
SELECT
  p.id         AS plasmid_id,
  p.code       AS plasmid_code,
  p.name       AS plasmid_name,
  p.created_at AS created_at,
  COALESCE(
    string_agg(DISTINCT fl.fluor_code, ', ' ORDER BY fl.fluor_code)
      FILTER (WHERE fl.id IS NOT NULL),
    ''
  ) AS fluors,
  COALESCE(
    string_agg(DISTINCT tg.tag_code, ', ' ORDER BY tg.tag_code)
      FILTER (WHERE tg.id IS NOT NULL),
    ''
  ) AS tags
FROM public.plasmids p
LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
LEFT JOIN public.fusions fu               ON fu.id          = jpf.fusion_id
LEFT JOIN public.fluors  fl               ON fl.id          = fu.fluor_id
LEFT JOIN public.tags    tg               ON tg.id          = fu.tag_id
GROUP BY p.id, p.code, p.name, p.created_at;

COMMIT;

BEGIN;
DROP VIEW IF EXISTS public.v_plasmids;
CREATE VIEW public.v_plasmids AS
SELECT
  p.id,
  p.code,
  p.name,
  p.nickname,
  p.resistance,
  p.supports_invitro_rna,
  p.notes,
  p.created_by,
  p.created_at,
  COALESCE(string_agg(DISTINCT fl.fluor_name, ',' ORDER BY fl.fluor_name)
           FILTER (WHERE fl.fluor_name IS NOT NULL), '')                           AS fluors,
  COALESCE(string_agg(DISTINCT tg.tag_name,   ',' ORDER BY tg.tag_name)
           FILTER (WHERE tg.tag_name   IS NOT NULL), '')                           AS tags,
  COALESCE(string_agg(DISTINCT fu.fusion_name,',' ORDER BY fu.fusion_name)
           FILTER (WHERE fu.fusion_name IS NOT NULL), '')                          AS fusions,
  COALESCE(array_remove(array_agg(DISTINCT fl.fluor_name), NULL), ARRAY[]::text[]) AS fluors_arr,
  COALESCE(array_remove(array_agg(DISTINCT tg.tag_name),   NULL), ARRAY[]::text[]) AS tags_arr,
  COALESCE(array_remove(array_agg(DISTINCT fu.fusion_name),NULL), ARRAY[]::text[]) AS fusions_arr
FROM public.plasmids p
LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
LEFT JOIN public.fusions fu               ON fu.id = jpf.fusion_id
LEFT JOIN public.fluors  fl               ON fl.id = fu.fluor_id
LEFT JOIN public.tags    tg               ON tg.id = fu.tag_id
GROUP BY
  p.id, p.code, p.name, p.nickname, p.resistance, p.supports_invitro_rna,
  p.notes, p.created_by, p.created_at;
COMMIT;

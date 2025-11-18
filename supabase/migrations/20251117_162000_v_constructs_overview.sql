BEGIN;

DROP VIEW IF EXISTS public.v_constructs_overview;

CREATE VIEW public.v_constructs_overview AS
SELECT
  p.code                               AS construct_code,
  COALESCE(p.name, '')                 AS construct_name,
  COALESCE(p.nickname, '')             AS construct_nickname,
  COALESCE(p.notes, '')                AS construct_notes,
  COALESCE(v.fluors, '')               AS fluors,
  COALESCE(v.tag_codes, '')            AS tag_codes,
  COALESCE(v.fusions, '')              AS fusions,
  COALESCE(v.n_fusions, 0)             AS n_fusions,
  p.created_at
FROM public.plasmids p
LEFT JOIN public.v_plasmids_overview v
       ON v.code = p.code
ORDER BY p.created_at DESC NULLS LAST, p.code;

COMMIT;

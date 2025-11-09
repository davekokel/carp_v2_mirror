BEGIN;

DROP VIEW IF EXISTS public.v_plasmids_rich;
DROP VIEW IF EXISTS public.v_plasmids;

ALTER TABLE public.plasmids
  DROP COLUMN IF EXISTS supports_invitro_rna;

CREATE VIEW public.v_plasmids AS
WITH agg AS (
  SELECT
    p.id,
    COALESCE(string_agg(DISTINCT fl.fluor_name, ',' ORDER BY fl.fluor_name), '') AS fluors,
    COALESCE(string_agg(DISTINCT tg.tag_name,   ',' ORDER BY tg.tag_name),   '') AS tags,
    COALESCE(string_agg(DISTINCT fu.fusion_name,',' ORDER BY fu.fusion_name), '') AS fusions,
    COALESCE(array_agg(DISTINCT fl.fluor_name) FILTER (WHERE fl.fluor_name IS NOT NULL), ARRAY[]::text[]) AS fluors_arr,
    COALESCE(array_agg(DISTINCT tg.tag_name)   FILTER (WHERE tg.tag_name   IS NOT NULL), ARRAY[]::text[]) AS tags_arr,
    COALESCE(array_agg(DISTINCT fu.fusion_name)FILTER (WHERE fu.fusion_name IS NOT NULL), ARRAY[]::text[]) AS fusions_arr
  FROM public.plasmids p
  LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
  LEFT JOIN public.fusions fu              ON fu.id = jpf.fusion_id
  LEFT JOIN public.fluors fl               ON fl.id = fu.fluor_id
  LEFT JOIN public.tags   tg               ON tg.id = fu.tag_id
  GROUP BY p.id
)
SELECT
  p.id,
  p.code,
  p.name,
  p.nickname,
  p.resistance,
  COALESCE(p.notes,'')          AS notes,
  p.created_by,
  p.created_at,
  COALESCE(a.fluors,'')         AS fluors,
  COALESCE(a.tags,'')           AS tags,
  COALESCE(a.fusions,'')        AS fusions,
  a.fluors_arr,
  a.tags_arr,
  a.fusions_arr
FROM public.plasmids p
LEFT JOIN agg a ON a.id = p.id;

CREATE VIEW public.v_plasmids_rich AS
WITH links AS (
  SELECT
    p.id AS plasmid_id,
    p.code AS plasmid_code,
    COALESCE(f.fusion_code, '') AS fusion_code,
    COALESCE(fl.fluor_name, fl.fluor_code, '') AS fluor_name,
    COALESCE(tg.tag_name,   tg.tag_code,   '') AS tag_name
  FROM public.plasmids p
  LEFT JOIN public.join_plasmid_fusions j ON j.plasmid_id = p.id
  LEFT JOIN public.fusions f              ON f.id = j.fusion_id
  LEFT JOIN public.fluors  fl             ON fl.id = f.fluor_id
  LEFT JOIN public.tags    tg             ON tg.id = f.tag_id
),
agg AS (
  SELECT
    l.plasmid_id,
    l.plasmid_code,
    COALESCE(NULLIF(string_agg(DISTINCT l.fusion_code, ', '), ''), '') AS fusion_names,
    COALESCE(NULLIF(string_agg(DISTINCT l.fluor_name, ', '), ''), '')  AS fluor_names,
    COALESCE(NULLIF(string_agg(DISTINCT l.tag_name,   ', '), ''), '')  AS tag_names
  FROM links l
  GROUP BY l.plasmid_id, l.plasmid_code
)
SELECT
  p.id                AS plasmid_id,
  p.code              AS plasmid_code,
  p.name              AS plasmid_name,
  COALESCE(p.nickname,'') AS nickname,
  COALESCE(a.fluor_names,'')  AS fluor_names,
  COALESCE(a.tag_names,'')    AS tag_names,
  COALESCE(a.fusion_names,'') AS fusion_names,
  COALESCE(p.resistance,'')   AS resistance,
  COALESCE(p.notes,'')        AS notes,
  p.created_by,
  p.created_at
FROM public.plasmids p
LEFT JOIN agg a ON a.plasmid_id = p.id
ORDER BY p.code;

COMMIT;

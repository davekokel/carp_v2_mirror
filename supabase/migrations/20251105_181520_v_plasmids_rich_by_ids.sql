BEGIN;
DROP VIEW IF EXISTS public.v_plasmids_rich;
CREATE VIEW public.v_plasmids_rich
(code, name, nickname, fluors, tags, fusions, fusion_names_pretty, resistance, supports_invitro_rna, notes, created_by, created_at)
AS
WITH links AS (
  SELECT
    p.id                       AS plasmid_id,
    f.id                       AS fusion_id,
    COALESCE(fl.fluor_name,'') AS fluor_name,
    COALESCE(tg.tag_name,'')   AS tag_name,
    f.fusion_code              AS fusion_code,
    COALESCE(f.fusion_name,'') AS fusion_name
  FROM public.join_plasmid_fusions j
  JOIN public.plasmids p ON p.id = j.plasmid_id
  JOIN public.fusions  f ON f.id = j.fusion_id
  LEFT JOIN public.fluors fl ON fl.id = f.fluor_id
  LEFT JOIN public.tags   tg ON tg.id = f.tag_id
),
labels AS (
  SELECT
    plasmid_id,
    CASE
      WHEN fluor_name <> '' AND tag_name <> '' THEN fluor_name || '::' || tag_name
      WHEN fluor_name <> '' THEN fluor_name
      WHEN tag_name  <> '' THEN tag_name
      ELSE ''
    END AS fusion_label,
    fusion_code,
    fluor_name,
    tag_name
  FROM links
),
agg AS (
  SELECT
    l.plasmid_id,
    string_agg(DISTINCT NULLIF(l.fluor_name,''), ', ' ORDER BY NULLIF(l.fluor_name,'')) AS fluors,
    string_agg(DISTINCT NULLIF(l.tag_name,''  ), ', ' ORDER BY NULLIF(l.tag_name,''  )) AS tags,
    string_agg(DISTINCT l.fusion_code, ', ' ORDER BY l.fusion_code) AS fusions,
    string_agg(DISTINCT NULLIF(l.fusion_label,''), ', ' ORDER BY NULLIF(l.fusion_label,'')) AS fusion_names_pretty
  FROM labels l
  GROUP BY l.plasmid_id
)
SELECT
  p.code,
  p.name,
  p.nickname,
  COALESCE(a.fluors,'')  AS fluors,
  COALESCE(a.tags,'')    AS tags,
  COALESCE(a.fusions,'') AS fusions,
  COALESCE(a.fusion_names_pretty,'') AS fusion_names_pretty,
  p.resistance,
  p.supports_invitro_rna,
  p.notes,
  p.created_by,
  p.created_at
FROM public.plasmids p
LEFT JOIN agg a ON a.plasmid_id = p.id;
COMMIT;

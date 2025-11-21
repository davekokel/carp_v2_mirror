BEGIN;

CREATE OR REPLACE VIEW public.v_plasmids_overview AS
WITH base AS (
  SELECT
    p.code,
    p.name,
    p.nickname,
    p.construct_type,
    p.created_at
  FROM public.plasmids p
),
fusion_rows AS (
  SELECT
    p.code AS plasmid_code,
    fl.fluor_code,
    tg.tag_code,
    fu.id AS fusion_id,
    fu.tag_pos,
    CASE
      WHEN fl.fluor_code IS NULL OR fl.fluor_code = '' THEN ''
      WHEN tg.tag_code IS NOT NULL AND tg.tag_code <> '' AND fu.tag_pos IS NOT NULL AND fu.tag_pos <> '' THEN
        fl.fluor_code || '::' || tg.tag_code || '(' || fu.tag_pos || ')'
      WHEN tg.tag_code IS NOT NULL AND tg.tag_code <> '' THEN
        fl.fluor_code || '::' || tg.tag_code
      ELSE
        fl.fluor_code
    END AS fusion_label
  FROM public.join_plasmid_fusions jpf
  JOIN public.plasmids p
    ON p.id = jpf.plasmid_id
  LEFT JOIN public.fusions fu
    ON fu.id = jpf.fusion_id
  LEFT JOIN public.fluors fl
    ON fl.id = fu.fluor_id
  LEFT JOIN public.tags tg
    ON tg.id = fu.tag_id
),
fused AS (
  SELECT
    plasmid_code,
    string_agg(DISTINCT fluor_code, ', ' ORDER BY fluor_code)       AS fluors,
    string_agg(DISTINCT tag_code, ', ' ORDER BY tag_code)           AS tag_codes,
    string_agg(DISTINCT fusion_label, ', ' ORDER BY fusion_label)   AS fusions,
    count(DISTINCT fusion_id)                                       AS n_fusions
  FROM fusion_rows
  GROUP BY plasmid_code
)
SELECT
  b.code,
  b.name,
  b.nickname,
  COALESCE(f.fluors, '')    AS fluors,
  COALESCE(f.tag_codes, '') AS tag_codes,
  COALESCE(f.fusions, '')   AS fusions,
  COALESCE(f.n_fusions, 0)  AS n_fusions,
  b.created_at,
  b.construct_type
FROM base b
LEFT JOIN fused f
  ON f.plasmid_code = b.code;

COMMIT;

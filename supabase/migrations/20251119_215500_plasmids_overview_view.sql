BEGIN;

CREATE OR REPLACE VIEW public.v_plasmids_overview AS
WITH base AS (
  SELECT
    p.code,
    p.name,
    p.nickname,
    p.created_at
  FROM public.plasmids p
),
fused AS (
  SELECT
    jpf.plasmid_code,
    string_agg(DISTINCT fl.fluor_code, ', ' ORDER BY fl.fluor_code) AS fluors,
    string_agg(DISTINCT tg.tag_code, ', ' ORDER BY tg.tag_code)      AS tag_codes,
    string_agg(DISTINCT fu.code, ', ' ORDER BY fu.code)              AS fusions,
    count(DISTINCT fu.id)                                            AS n_fusions
  FROM public.join_plasmid_fusions jpf
  LEFT JOIN public.fusions fu ON fu.id = jpf.fusion_id
  LEFT JOIN public.fluors fl  ON fl.id = fu.fluor_id
  LEFT JOIN public.tags tg    ON tg.id = fu.tag_id
  GROUP BY jpf.plasmid_code
)
SELECT
  b.code,
  b.name,
  b.nickname,
  COALESCE(f.fluors, '')    AS fluors,
  COALESCE(f.tag_codes, '') AS tag_codes,
  COALESCE(f.fusions, '')   AS fusions,
  COALESCE(f.n_fusions, 0)  AS n_fusions,
  b.created_at
FROM base b
LEFT JOIN fused f
  ON f.plasmid_code = b.code;

COMMIT;

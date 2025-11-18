BEGIN;

DROP VIEW IF EXISTS public.v_plasmids_overview;

CREATE VIEW public.v_plasmids_overview AS
WITH fusion_rows AS (
  -- Fusions wired directly to plasmids
  SELECT
    p.id AS plasmid_id,
    f.id AS fusion_id
  FROM public.plasmids p
  LEFT JOIN public.join_plasmid_fusions jpf
         ON jpf.plasmid_id = p.id
  LEFT JOIN public.fusions f
         ON f.id = jpf.fusion_id

  UNION ALL

  -- Fusions wired via RNAs that share the same base code
  SELECT
    p.id AS plasmid_id,
    f.id AS fusion_id
  FROM public.plasmids p
  JOIN public.rnas r
    ON r.rna_base_code = p.plasmid_base_code
  JOIN public.join_rna_fusions jrf
    ON jrf.rna_id = r.id
  JOIN public.fusions f
    ON f.id = jrf.fusion_id
),
fusion_enriched AS (
  SELECT
    fr.plasmid_id,
    fr.fusion_id,
    fl.fluor_code,
    tg.tag_code,
    vfl.fusion_label
  FROM fusion_rows fr
  JOIN public.fusions f
    ON f.id = fr.fusion_id
  LEFT JOIN public.fluors fl
    ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg
    ON tg.id = f.tag_id
  LEFT JOIN public.v_fusion_labels vfl
    ON vfl.fusion_id = f.id
),
fusion_rollup AS (
  SELECT
    plasmid_id,
    string_agg(DISTINCT fluor_code,   ', ' ORDER BY fluor_code)   AS fluors,
    string_agg(DISTINCT tag_code,     ', ' ORDER BY tag_code)     AS tag_codes,
    string_agg(DISTINCT fusion_label, ', ' ORDER BY fusion_label) AS fusions,
    COUNT(DISTINCT fusion_id) AS n_fusions
  FROM fusion_enriched
  WHERE fusion_id IS NOT NULL
  GROUP BY plasmid_id
)
SELECT
  p.code,
  p.name,
  p.nickname,
  fr.fluors,
  fr.tag_codes,
  fr.fusions,
  COALESCE(fr.n_fusions, 0) AS n_fusions,
  p.created_at
FROM public.plasmids p
LEFT JOIN fusion_rollup fr
       ON fr.plasmid_id = p.id
ORDER BY p.created_at DESC NULLS LAST, p.code;

COMMIT;

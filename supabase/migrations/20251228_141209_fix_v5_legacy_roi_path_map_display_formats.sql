BEGIN;

DROP VIEW IF EXISTS public.v_legacy_roi_path_map_v5_display;

CREATE VIEW public.v_legacy_roi_path_map_v5_display AS
WITH geno_tok AS (
  SELECT
    g.roi_path,
    CASE
      WHEN coalesce(nullif(btrim(g.allele_code), ''), '') = '' THEN
        'tg(' || g.construct_base_code || ')'
      ELSE
        'tg(' || g.construct_base_code || ')' || g.allele_code
    END AS tg_token
  FROM public.legacy_roi_genotype_constructs_v5 g
),
geno AS (
  SELECT
    roi_path,
    string_agg(DISTINCT tg_token, '; ' ORDER BY tg_token) AS tg_display
  FROM geno_tok
  GROUP BY roi_path
),
ft_tok AS (
  SELECT
    g.roi_path,
    CASE
      WHEN coalesce(nullif(btrim(fl.display_name), ''), '') = '' THEN NULL
      ELSE
        fl.display_name
        || '-'
        || coalesce(
             nullif(btrim(to_jsonb(tg)->>'display_name'), ''),
             nullif(btrim(to_jsonb(tg)->>'name'), ''),
             nullif(btrim(to_jsonb(tg)->>'tag_code'), ''),
             nullif(btrim(to_jsonb(tg)->>'code'), '')
           )
        || CASE
             WHEN coalesce(nullif(btrim(to_jsonb(tg)->>'tag_pos'), ''), '') <> '' THEN '(' || (to_jsonb(tg)->>'tag_pos') || ')'
             ELSE ''
           END
    END AS fluortag_token
  FROM public.legacy_roi_genotype_constructs_v5 g
  JOIN public.constructs c ON c.base_code = g.construct_base_code
  JOIN public.construct_fusions cf ON cf.construct_id = c.id
  JOIN public.fusions f ON f.id = cf.fusion_id
  LEFT JOIN public.fluors fl ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg ON tg.id = f.tag_id
),
ft AS (
  SELECT
    roi_path,
    string_agg(DISTINCT fluortag_token, '; ' ORDER BY fluortag_token) FILTER (WHERE fluortag_token IS NOT NULL) AS fluortag_display
  FROM ft_tok
  GROUP BY roi_path
),
fo_tok AS (
  SELECT
    g.roi_path,
    (fl.display_name || '-' || tg.localization) AS fluororganelle_token
  FROM public.legacy_roi_genotype_constructs_v5 g
  JOIN public.constructs c ON c.base_code = g.construct_base_code
  JOIN public.construct_fusions cf ON cf.construct_id = c.id
  JOIN public.fusions f ON f.id = cf.fusion_id
  LEFT JOIN public.fluors fl ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg ON tg.id = f.tag_id
  WHERE coalesce(nullif(btrim(fl.display_name), ''), '') <> ''
    AND coalesce(nullif(btrim(tg.localization), ''), '') <> ''
),
fo AS (
  SELECT
    roi_path,
    string_agg(DISTINCT fluororganelle_token, '; ' ORDER BY fluororganelle_token) AS fluororganelle_display
  FROM fo_tok
  GROUP BY roi_path
),
tx_tok AS (
  SELECT
    roi_path,
    CASE
      WHEN kind = 'rna' THEN 'rna(' || construct_base_code || ')'
      WHEN kind = 'plasmid' THEN 'plasmid(' || construct_base_code || ')'
      WHEN kind = 'crispr' THEN 'crispr(' || construct_base_code || ')'
      ELSE kind || '(' || construct_base_code || ')'
    END AS tx_token
  FROM public.legacy_roi_treatment_constructs_v5
),
tx AS (
  SELECT
    roi_path,
    string_agg(DISTINCT tx_token, '; ' ORDER BY tx_token) AS treatment_display
  FROM tx_tok
  GROUP BY roi_path
)
SELECT
  m.roi_path,
  coalesce(geno.tg_display, '') AS tg_display,
  coalesce(ft.fluortag_display, '') AS fluortag_display,
  coalesce(fo.fluororganelle_display, '') AS fluororganelle_display,
  coalesce(tx.treatment_display, '') AS treatment_display,
  m.date_mount_id,
  m.genotype_base_codes,
  m.genotype_allele_codes,
  m.treatment_rna_base_codes,
  m.treatment_plasmid_base_codes
FROM public.legacy_roi_path_map_v5 m
LEFT JOIN geno USING (roi_path)
LEFT JOIN ft USING (roi_path)
LEFT JOIN fo USING (roi_path)
LEFT JOIN tx USING (roi_path);

COMMIT;

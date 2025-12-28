BEGIN;

DROP VIEW IF EXISTS public.v_legacy_roi_path_map_v5_display;

CREATE VIEW public.v_legacy_roi_path_map_v5_display AS
WITH geno_tok AS (
  SELECT
    g.roi_path,
    CASE
      WHEN coalesce(nullif(btrim(g.allele_code), ''), '') <> '' THEN
        'tg(' || g.construct_base_code || ')' ||
        coalesce(nullif(btrim(ta.allele_name), ''), '') ||
        '-' || g.allele_code
      ELSE
        'tg(' || g.construct_base_code || ')'
    END AS tg_token
  FROM public.legacy_roi_genotype_constructs_v5 g
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = g.construct_base_code
   AND ta.allele_nickname = nullif(btrim(g.allele_code), '')
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
      WHEN coalesce(nullif(btrim(fl.display_name), ''), '') <> ''
       AND coalesce(nullif(btrim(tg.display_name), ''), '') <> '' THEN
        fl.display_name || '-' || tg.display_name ||
        CASE WHEN coalesce(nullif(btrim(f.tag_pos), ''), '') <> '' THEN '(' || f.tag_pos || ')' ELSE '' END
      WHEN coalesce(nullif(btrim(f.display_name), ''), '') <> '' THEN
        f.display_name
      ELSE
        NULL
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
    string_agg(DISTINCT fluortag_token, '; ' ORDER BY fluortag_token) AS fluortag_display
  FROM ft_tok
  WHERE fluortag_token IS NOT NULL AND btrim(fluortag_token) <> ''
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
    (kind || '(' || construct_base_code || ')') AS tx_token
  FROM public.legacy_roi_treatment_constructs_v5
  WHERE coalesce(nullif(btrim(kind), ''), '') <> ''
    AND coalesce(nullif(btrim(construct_base_code), ''), '') <> ''
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

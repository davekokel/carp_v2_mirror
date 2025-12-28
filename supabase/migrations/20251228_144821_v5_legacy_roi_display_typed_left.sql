BEGIN;

CREATE OR REPLACE VIEW public.v_legacy_roi_path_map_v5_display AS
WITH
geno_tok AS (
  SELECT
    g.roi_path,
    CASE
      WHEN coalesce(nullif(btrim(g.allele_code), ''), '') <> '' THEN
        'tg(' || g.construct_base_code || ')' || ta.allele_name || '-' || g.allele_code
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
    string_agg(DISTINCT tg_token, '; ' ORDER BY tg_token) AS tg_right
  FROM geno_tok
  WHERE coalesce(nullif(btrim(tg_token), ''), '') <> ''
  GROUP BY roi_path
),

ft_tok AS (
  SELECT
    g.roi_path,
    CASE
      WHEN f.tag_pos IS NOT NULL AND coalesce(nullif(btrim(f.tag_pos), ''), '') <> '' THEN f.display_name || '(' || f.tag_pos || ')'
      ELSE f.display_name
    END AS ft_token
  FROM public.legacy_roi_genotype_constructs_v5 g
  JOIN public.constructs c ON c.base_code = g.construct_base_code
  JOIN public.construct_fusions cf ON cf.construct_id = c.id
  JOIN public.fusions f ON f.id = cf.fusion_id
  WHERE coalesce(nullif(btrim(f.display_name), ''), '') <> ''
),
ft AS (
  SELECT
    roi_path,
    string_agg(DISTINCT ft_token, '; ' ORDER BY ft_token) AS ft_right
  FROM ft_tok
  GROUP BY roi_path
),

fo_tok AS (
  SELECT
    g.roi_path,
    (fl.display_name || '-' || tg.localization) AS fo_token
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
    string_agg(DISTINCT fo_token, '; ' ORDER BY fo_token) AS fo_right
  FROM fo_tok
  GROUP BY roi_path
),

tx_base AS (
  SELECT
    t.roi_path,
    t.kind,
    t.construct_base_code
  FROM public.legacy_roi_treatment_constructs_v5 t
),

tx_tg AS (
  SELECT
    roi_path,
    string_agg(DISTINCT (kind || '(' || construct_base_code || ')'), '; ' ORDER BY (kind || '(' || construct_base_code || ')')) AS tg_left
  FROM tx_base
  GROUP BY roi_path
),

tx_ft_tok AS (
  SELECT
    t.roi_path,
    t.kind,
    CASE
      WHEN f.tag_pos IS NOT NULL AND coalesce(nullif(btrim(f.tag_pos), ''), '') <> '' THEN f.display_name || '(' || f.tag_pos || ')'
      ELSE f.display_name
    END AS ft_token
  FROM tx_base t
  JOIN public.constructs c ON c.base_code = t.construct_base_code
  JOIN public.construct_fusions cf ON cf.construct_id = c.id
  JOIN public.fusions f ON f.id = cf.fusion_id
  WHERE coalesce(nullif(btrim(f.display_name), ''), '') <> ''
),
tx_ft AS (
  SELECT
    roi_path,
    string_agg(DISTINCT (kind || '(' || ft_token || ')'), '; ' ORDER BY (kind || '(' || ft_token || ')')) AS ft_left
  FROM tx_ft_tok
  GROUP BY roi_path
),

tx_fo_tok AS (
  SELECT
    t.roi_path,
    t.kind,
    (fl.display_name || '-' || tg.localization) AS fo_token
  FROM tx_base t
  JOIN public.constructs c ON c.base_code = t.construct_base_code
  JOIN public.construct_fusions cf ON cf.construct_id = c.id
  JOIN public.fusions f ON f.id = cf.fusion_id
  LEFT JOIN public.fluors fl ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg ON tg.id = f.tag_id
  WHERE coalesce(nullif(btrim(fl.display_name), ''), '') <> ''
    AND coalesce(nullif(btrim(tg.localization), ''), '') <> ''
),
tx_fo AS (
  SELECT
    roi_path,
    string_agg(DISTINCT (kind || '(' || fo_token || ')'), '; ' ORDER BY (kind || '(' || fo_token || ')')) AS fo_left
  FROM tx_fo_tok
  GROUP BY roi_path
),

tx_any AS (
  SELECT
    roi_path,
    string_agg(DISTINCT (kind || '(' || construct_base_code || ')'), '; ' ORDER BY (kind || '(' || construct_base_code || ')')) AS treatment_display
  FROM tx_base
  GROUP BY roi_path
)

SELECT
  m.roi_path,

  CASE
    WHEN coalesce(nullif(btrim(tx_tg.tg_left), ''), '') <> '' AND coalesce(nullif(btrim(geno.tg_right), ''), '') <> ''
      THEN tx_tg.tg_left || ' > ' || geno.tg_right
    WHEN coalesce(nullif(btrim(tx_tg.tg_left), ''), '') <> ''
      THEN tx_tg.tg_left
    ELSE coalesce(geno.tg_right, '')
  END AS tg_display,

  CASE
    WHEN coalesce(nullif(btrim(tx_ft.ft_left), ''), '') <> '' AND coalesce(nullif(btrim(ft.ft_right), ''), '') <> ''
      THEN tx_ft.ft_left || ' > ' || ft.ft_right
    WHEN coalesce(nullif(btrim(tx_ft.ft_left), ''), '') <> ''
      THEN tx_ft.ft_left
    ELSE coalesce(ft.ft_right, '')
  END AS fluortag_display,

  CASE
    WHEN coalesce(nullif(btrim(tx_fo.fo_left), ''), '') <> '' AND coalesce(nullif(btrim(fo.fo_right), ''), '') <> ''
      THEN tx_fo.fo_left || ' > ' || fo.fo_right
    WHEN coalesce(nullif(btrim(tx_fo.fo_left), ''), '') <> ''
      THEN tx_fo.fo_left
    ELSE coalesce(fo.fo_right, '')
  END AS fluororganelle_display,

  coalesce(tx_any.treatment_display, '') AS treatment_display,

  m.date_mount_id,
  m.genotype_base_codes,
  m.genotype_allele_codes,
  m.treatment_rna_base_codes,
  m.treatment_plasmid_base_codes

FROM public.legacy_roi_path_map_v5 m
LEFT JOIN geno   USING (roi_path)
LEFT JOIN ft     USING (roi_path)
LEFT JOIN fo     USING (roi_path)
LEFT JOIN tx_tg  USING (roi_path)
LEFT JOIN tx_ft  USING (roi_path)
LEFT JOIN tx_fo  USING (roi_path)
LEFT JOIN tx_any USING (roi_path);

COMMIT;

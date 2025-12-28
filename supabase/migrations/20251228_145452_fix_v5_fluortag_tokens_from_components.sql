BEGIN;

CREATE OR REPLACE VIEW public.v_legacy_roi_path_map_v5_display AS
WITH
geno_tok AS (
  SELECT
    roi_path,
    CASE
      WHEN coalesce(nullif(btrim(g.allele_code), ''), '') <> '' THEN
        'tg(' || g.construct_base_code || ')' ||
        coalesce(nullif(ta.allele_name,''), '') || '-' || g.allele_code
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
      WHEN coalesce(nullif(btrim(f.tag_pos::text), ''), '') <> '' THEN
        (coalesce(nullif(btrim(f.display_name), ''), (fl.display_name || '-' || tg.display_name)) || '(' || f.tag_pos::text || ')')
      ELSE
        coalesce(nullif(btrim(f.display_name), ''), (fl.display_name || '-' || tg.display_name))
    END AS fluortag_token
  FROM public.legacy_roi_genotype_constructs_v5 g
  JOIN public.constructs c ON c.base_code = g.construct_base_code
  JOIN public.construct_fusions cf ON cf.construct_id = c.id
  JOIN public.fusions f ON f.id = cf.fusion_id
  LEFT JOIN public.fluors fl ON fl.id = f.fluor_id
  LEFT JOIN public.tags  tg ON tg.id = f.tag_id
  WHERE coalesce(nullif(btrim(coalesce(nullif(btrim(f.display_name), ''), (fl.display_name || '-' || tg.display_name))), ''), '') <> ''
),
ft AS (
  SELECT
    roi_path,
    string_agg(DISTINCT fluortag_token, '; ' ORDER BY fluortag_token) AS fluortag_display
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

tx_kind AS (
  SELECT
    roi_path,
    CASE
      WHEN count(DISTINCT kind) = 1 THEN min(kind)
      ELSE 'na'
    END AS wrap_kind
  FROM public.legacy_roi_treatment_constructs_v5
  GROUP BY roi_path
),

tx_tg AS (
  SELECT
    t.roi_path,
    string_agg(DISTINCT (k.wrap_kind || '(' || t.construct_base_code || ')'), '; ' ORDER BY (k.wrap_kind || '(' || t.construct_base_code || ')')) AS treatment_tg_left
  FROM public.legacy_roi_treatment_constructs_v5 t
  JOIN tx_kind k USING (roi_path)
  GROUP BY t.roi_path, k.wrap_kind
),

tx_fo_tok AS (
  SELECT
    t.roi_path,
    (fl.display_name || '-' || tg.localization) AS fo_token
  FROM public.legacy_roi_treatment_constructs_v5 t
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
    x.roi_path,
    string_agg(DISTINCT (k.wrap_kind || '(' || x.fo_token || ')'), '; ' ORDER BY (k.wrap_kind || '(' || x.fo_token || ')')) AS treatment_fo_left
  FROM tx_fo_tok x
  JOIN tx_kind k USING (roi_path)
  GROUP BY x.roi_path, k.wrap_kind
),

tx_ft_tok AS (
  SELECT
    t.roi_path,
    CASE
      WHEN coalesce(nullif(btrim(f.tag_pos::text), ''), '') <> '' THEN
        (coalesce(nullif(btrim(f.display_name), ''), (fl.display_name || '-' || tg.display_name)) || '(' || f.tag_pos::text || ')')
      ELSE
        coalesce(nullif(btrim(f.display_name), ''), (fl.display_name || '-' || tg.display_name))
    END AS ft_token
  FROM public.legacy_roi_treatment_constructs_v5 t
  JOIN public.constructs c ON c.base_code = t.construct_base_code
  JOIN public.construct_fusions cf ON cf.construct_id = c.id
  JOIN public.fusions f ON f.id = cf.fusion_id
  LEFT JOIN public.fluors fl ON fl.id = f.fluor_id
  LEFT JOIN public.tags  tg ON tg.id = f.tag_id
  WHERE coalesce(nullif(btrim(coalesce(nullif(btrim(f.display_name), ''), (fl.display_name || '-' || tg.display_name))), ''), '') <> ''
),
tx_ft AS (
  SELECT
    x.roi_path,
    string_agg(DISTINCT (k.wrap_kind || '(' || x.ft_token || ')'), '; ' ORDER BY (k.wrap_kind || '(' || x.ft_token || ')')) AS treatment_ft_left
  FROM tx_ft_tok x
  JOIN tx_kind k USING (roi_path)
  GROUP BY x.roi_path, k.wrap_kind
),

tx_any AS (
  SELECT
    roi_path,
    string_agg(DISTINCT (kind || '(' || construct_base_code || ')'), '; ' ORDER BY (kind || '(' || construct_base_code || ')')) AS treatment_display
  FROM public.legacy_roi_treatment_constructs_v5
  GROUP BY roi_path
)

SELECT
  m.roi_path,

  CASE
    WHEN coalesce(nullif(btrim(tx_tg.treatment_tg_left), ''), '') <> '' AND coalesce(nullif(btrim(geno.tg_display), ''), '') <> ''
      THEN tx_tg.treatment_tg_left || ' > ' || geno.tg_display
    WHEN coalesce(nullif(btrim(tx_tg.treatment_tg_left), ''), '') <> ''
      THEN tx_tg.treatment_tg_left
    ELSE coalesce(geno.tg_display, '')
  END AS tg_display,

  CASE
    WHEN coalesce(nullif(btrim(tx_ft.treatment_ft_left), ''), '') <> '' AND coalesce(nullif(btrim(ft.fluortag_display), ''), '') <> ''
      THEN tx_ft.treatment_ft_left || ' > ' || ft.fluortag_display
    WHEN coalesce(nullif(btrim(tx_ft.treatment_ft_left), ''), '') <> ''
      THEN tx_ft.treatment_ft_left
    ELSE coalesce(ft.fluortag_display, '')
  END AS fluortag_display,

  CASE
    WHEN coalesce(nullif(btrim(tx_fo.treatment_fo_left), ''), '') <> '' AND coalesce(nullif(btrim(fo.fluororganelle_display), ''), '') <> ''
      THEN tx_fo.treatment_fo_left || ' > ' || fo.fluororganelle_display
    WHEN coalesce(nullif(btrim(tx_fo.treatment_fo_left), ''), '') <> ''
      THEN tx_fo.treatment_fo_left
    ELSE coalesce(fo.fluororganelle_display, '')
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

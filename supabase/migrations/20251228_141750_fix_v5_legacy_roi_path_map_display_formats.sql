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
        'tg(' || g.construct_base_code || ')' ||
        coalesce(
          nullif(btrim(ta.allele_nickname), ''),
          nullif(btrim(ta.display_name), ''),
          nullif(btrim(ta.allele_name), ''),
          nullif(btrim(ta.nickname), ''),
          g.allele_code
        )
    END AS tg_token
  FROM public.legacy_roi_genotype_constructs_v5 g
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = g.construct_base_code
   AND (
        (g.allele_code ~ '^[0-9]+$' AND ta.allele_number = g.allele_code::int)
        OR lower(coalesce(ta.allele_nickname, '')) = lower(g.allele_code)
        OR lower(coalesce(ta.nickname, '')) = lower(g.allele_code)
      )
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
    (
      coalesce(nullif(btrim(fl.display_name), ''), '') || '-' ||
      coalesce(
        nullif(btrim(tg.display_name), ''),
        nullif(btrim(tg.code), ''),
        nullif(btrim(tg.nickname), '')
      ) ||
      '(' || coalesce(nullif(btrim(f.tag_pos), ''), '?') || ')'
    ) AS fluortag_token
  FROM public.legacy_roi_genotype_constructs_v5 g
  JOIN public.constructs c ON c.base_code = g.construct_base_code
  JOIN public.construct_fusions cf ON cf.construct_id = c.id
  JOIN public.fusions f ON f.id = cf.fusion_id
  LEFT JOIN public.fluors fl ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg ON tg.id = f.tag_id
  WHERE coalesce(nullif(btrim(fl.display_name), ''), '') <> ''
    AND coalesce(nullif(btrim(tg.display_name), ''), nullif(btrim(tg.code), ''), nullif(btrim(tg.nickname), ''), '') <> ''
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
tx AS (
  SELECT
    roi_path,
    string_agg(
      DISTINCT (kind || '(' || construct_base_code || ')'),
      '; ' ORDER BY (kind || '(' || construct_base_code || ')')
    ) AS treatment_display
  FROM public.legacy_roi_treatment_constructs_v5
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

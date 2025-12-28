BEGIN;

CREATE OR REPLACE VIEW public.v_legacy_roi_path_map_v5_display AS
WITH geno_tok AS (
  SELECT
    g.roi_path,
    CASE
      WHEN coalesce(nullif(btrim(g.allele_code), ''), '') <> '' THEN
        'tg(' || g.construct_base_code || ')' ||
        CASE
          WHEN g.allele_code ~ '^[0-9]+$'
               AND coalesce(nullif(btrim(c.series_prefix), ''), '') <> ''
            THEN c.series_prefix || g.allele_code
          ELSE g.allele_code
        END
      ELSE
        'tg(' || g.construct_base_code || ')'
    END AS tg_token
  FROM public.legacy_roi_genotype_constructs_v5 g
  LEFT JOIN public.constructs c
    ON c.base_code = g.construct_base_code
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
    COALESCE(
      NULLIF(btrim(f.display_name), ''),
      NULLIF(btrim((fl.display_name || '-' || tg.display_name)), ''),
      NULLIF(btrim((fl.display_name || '-' || tg.code)), ''),
      NULLIF(btrim((fl.code || '-' || tg.display_name)), ''),
      NULLIF(btrim((fl.code || '-' || tg.code)), '')
    ) AS fluortag_token
  FROM public.legacy_roi_genotype_constructs_v5 g
  JOIN public.constructs c ON c.base_code = g.construct_base_code
  JOIN public.construct_fusions cf ON cf.construct_id = c.id
  JOIN public.fusions f ON f.id = cf.fusion_id
  LEFT JOIN public.fluors fl ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg ON tg.id = f.tag_id
  WHERE COALESCE(
      NULLIF(btrim(f.display_name), ''),
      NULLIF(btrim((fl.display_name || '-' || tg.display_name)), ''),
      NULLIF(btrim((fl.display_name || '-' || tg.code)), ''),
      NULLIF(btrim((fl.code || '-' || tg.display_name)), ''),
      NULLIF(btrim((fl.code || '-' || tg.code)), '')
  ) IS NOT NULL
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
  m.date_mount_id,
  m.genotype_base_codes,
  m.genotype_allele_codes,
  m.treatment_rna_base_codes,
  m.treatment_plasmid_base_codes,
  coalesce(tx.treatment_display, '') AS treatment_display
FROM public.legacy_roi_path_map_v5 m
LEFT JOIN geno USING (roi_path)
LEFT JOIN ft USING (roi_path)
LEFT JOIN fo USING (roi_path)
LEFT JOIN tx USING (roi_path);

CREATE OR REPLACE VIEW public.v_legacy_roi_channels_v5_display AS
SELECT
  c.roi_path,
  c.channel_name,
  c.n_tiffs,
  c.decision_status,
  c.note
FROM public.legacy_roi_channels_v5 c;

COMMIT;

-- v5 ROI label fallback (roi_path keyed) that reuses canonical construct + transgene_alleles metadata
-- Goal: when clutch/genotype is missing, still render TG / FluorTag / FluorOrganelle from v5_* columns.

CREATE OR REPLACE VIEW public.v11_v5_roi_label_fallback AS
WITH ira AS (
  SELECT
    ra.id AS roi_id,
    ra.roi_path,
    ra.v5_genotype_base_codes,
    ra.v5_genotype_allele_codes
  FROM public.imaging_roi_annotations ra
),
base_raw AS (
  SELECT
    i.roi_id,
    i.roi_path,
    lower(btrim(tok.tok)) AS tok
  FROM ira i
  CROSS JOIN LATERAL regexp_split_to_table(COALESCE(i.v5_genotype_base_codes, ''), '[,;|[:space:]]+') tok(tok)
  WHERE NULLIF(btrim(tok.tok), '') IS NOT NULL
),
base_norm AS (
  SELECT
    br.roi_id,
    br.roi_path,
    CASE
      WHEN regexp_match(regexp_replace(br.tok, '[^a-z0-9\-]+', '', 'g'), '^([a-z]+)-?0*([0-9]+)$') IS NOT NULL
        THEN format(
          '%s-%s',
          (regexp_match(regexp_replace(br.tok, '[^a-z0-9\-]+', '', 'g'), '^([a-z]+)-?0*([0-9]+)$'))[1],
          ((regexp_match(regexp_replace(br.tok, '[^a-z0-9\-]+', '', 'g'), '^([a-z]+)-?0*([0-9]+)$'))[2])::int
        )
      ELSE regexp_replace(br.tok, '[^a-z0-9\-]+', '', 'g')
    END AS base_code_norm
  FROM base_raw br
  WHERE NULLIF(btrim(br.tok), '') IS NOT NULL
),
alle_raw AS (
  SELECT
    i.roi_id,
    i.roi_path,
    btrim(tok.tok) AS allele_tok,
    row_number() OVER (PARTITION BY i.roi_id ORDER BY (SELECT 1)) AS ord
  FROM ira i
  CROSS JOIN LATERAL regexp_split_to_table(COALESCE(i.v5_genotype_allele_codes, ''), '[,;|[:space:]]+') tok(tok)
  WHERE NULLIF(btrim(tok.tok), '') IS NOT NULL
),
base_ord AS (
  SELECT
    bn.roi_id,
    bn.roi_path,
    bn.base_code_norm,
    row_number() OVER (PARTITION BY bn.roi_id ORDER BY bn.base_code_norm) AS ord
  FROM base_norm bn
),
pairs AS (
  SELECT
    b.roi_id,
    b.roi_path,
    b.base_code_norm,
    a.allele_tok
  FROM base_ord b
  LEFT JOIN alle_raw a
    ON a.roi_id = b.roi_id AND a.ord = b.ord
),
tg_entries AS (
  SELECT
    p.roi_id,
    p.roi_path,
    p.base_code_norm,
    p.allele_tok,
    ta.allele_number,
    CASE
      WHEN NULLIF(btrim(ta.allele_name), '') IS NOT NULL AND NULLIF(btrim(ta.allele_nickname), '') IS NOT NULL THEN format('%s-%s', btrim(ta.allele_name), btrim(ta.allele_nickname))
      WHEN NULLIF(btrim(ta.allele_name), '') IS NOT NULL AND ta.allele_number IS NOT NULL THEN format('%s-%s', btrim(ta.allele_name), ta.allele_number)
      WHEN NULLIF(btrim(ta.allele_nickname), '') IS NOT NULL THEN btrim(ta.allele_nickname)
      WHEN NULLIF(btrim(ta.allele_name), '') IS NOT NULL THEN btrim(ta.allele_name)
      WHEN NULLIF(btrim(ta.nickname), '') IS NOT NULL THEN btrim(ta.nickname)
      WHEN NULLIF(btrim(ta.display_name), '') IS NOT NULL THEN btrim(ta.display_name)
      ELSE NULL
    END AS allele_suffix
  FROM pairs p
  LEFT JOIN public.transgene_alleles ta
    ON lower(ta.transgene_base_code) = p.base_code_norm
   AND (
        (p.allele_tok ~ '^[0-9]+$' AND ta.allele_number::text = p.allele_tok)
        OR (ta.allele_nickname IS NOT NULL AND btrim(ta.allele_nickname) = p.allele_tok)
      )
),
tg_labels AS (
  SELECT
    te.roi_id,
    te.base_code_norm,
    CASE
      WHEN te.allele_suffix IS NULL THEN format('tg(%s)', te.base_code_norm)
      ELSE format('tg(%s)%s', te.base_code_norm, te.allele_suffix)
    END AS tg_label
  FROM tg_entries te
),
tg_rollup AS (
  SELECT
    roi_id,
    NULLIF(string_agg(DISTINCT tg_label, '; ' ORDER BY tg_label), '') AS tg_style_canon
  FROM tg_labels
  GROUP BY roi_id
),
g_constructs AS (
  SELECT DISTINCT
    bn.roi_id,
    bn.base_code_norm,
    c.id AS construct_id
  FROM base_norm bn
  JOIN public.constructs c ON lower(c.base_code) = bn.base_code_norm
),
fusion_bits AS (
  SELECT
    gc.roi_id,
    COALESCE(fl.nickname, fl.display_name, fl.code) AS fluor_label,
    COALESCE(tg.nickname, tg.display_name, tg.code) AS tag_label,
    tg.localization,
    f.tag_pos,
    CASE
      WHEN tg.id IS NULL THEN COALESCE(fl.nickname, fl.display_name, fl.code)
      ELSE format('%s-%s(%s)', COALESCE(fl.nickname, fl.display_name, fl.code), COALESCE(tg.nickname, tg.display_name, tg.code), f.tag_pos)
    END AS fluor_tag_label,
    CASE
      WHEN tg.localization IS NULL OR tg.localization = '' THEN COALESCE(fl.nickname, fl.display_name, fl.code)
      ELSE format('%s-%s', COALESCE(fl.nickname, fl.display_name, fl.code), tg.localization)
    END AS organelle_fluor_label
  FROM g_constructs gc
  JOIN public.construct_fusions cf ON cf.construct_id = gc.construct_id
  JOIN public.fusions f ON f.id = cf.fusion_id
  JOIN public.fluors fl ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg ON tg.id = f.tag_id
),
fluor_tag_rollup AS (
  SELECT
    roi_id,
    NULLIF(string_agg(DISTINCT fluor_tag_label, '; ' ORDER BY fluor_tag_label), '') AS fluor_tag_style
  FROM fusion_bits
  GROUP BY roi_id
),
organelle_rollup AS (
  SELECT
    roi_id,
    NULLIF(string_agg(DISTINCT organelle_fluor_label, '; ' ORDER BY organelle_fluor_label), '') AS fluor_organelle_style
  FROM fusion_bits
  GROUP BY roi_id
)
SELECT
  i.roi_id,
  i.roi_path,
  tr.tg_style_canon,
  ft.fluor_tag_style,
  og.fluor_organelle_style
FROM ira i
LEFT JOIN tg_rollup tr ON tr.roi_id = i.roi_id
LEFT JOIN fluor_tag_rollup ft ON ft.roi_id = i.roi_id
LEFT JOIN organelle_rollup og ON og.roi_id = i.roi_id;


-- Patch ROI flat display to fall back to v5 labels when clutch/genotype chain is missing
CREATE OR REPLACE VIEW public.v11_roi_flat_table_display AS
SELECT
  t.experiment_date,
  t.experiment_name,
  t.plate_note,
  t.slot_note,
  t.slot_orientation,
  t.roi_id,
  t.roi_code,
  t.roi_index_within_slot,
  t.roi_note_anatomy,
  t.roi_path,
  ira.n_tiffs,
  t.clutch_code,
  count(DISTINCT t.treated_clutch_id) FILTER (WHERE t.treated_clutch_id IS NOT NULL) AS n_treated_clutches,
  string_agg(DISTINCT COALESCE(t.treated_clutch_code, tc.treated_clutch_code), '; ' ORDER BY (COALESCE(t.treated_clutch_code, tc.treated_clutch_code))) FILTER (WHERE COALESCE(t.treated_clutch_code, tc.treated_clutch_code) IS NOT NULL) AS treated_clutch_codes,
  string_agg(DISTINCT COALESCE(t.treatment_code, tr.treat_code), '; ' ORDER BY (COALESCE(t.treatment_code, tr.treat_code))) FILTER (WHERE COALESCE(t.treatment_code, tr.treat_code) IS NOT NULL) AS treatment_codes,
  string_agg(DISTINCT t.plasmids_display, '; ' ORDER BY t.plasmids_display) FILTER (WHERE t.plasmids_display IS NOT NULL) AS plasmids_display,
  string_agg(DISTINCT t.rnas_display, '; ' ORDER BY t.rnas_display) FILTER (WHERE t.rnas_display IS NOT NULL) AS rnas_display,
  string_agg(DISTINCT t.dyes_display, '; ' ORDER BY t.dyes_display) FILTER (WHERE t.dyes_display IS NOT NULL) AS dyes_display,

  -- genotype/treatment label display (canonical first, v5 fallback second)
  COALESCE(
    NULLIF(btrim(max(gl.tg_style_canon)), ''),
    NULLIF(btrim(max(v5.tg_style_canon)), '')
  ) AS tx_gt_tg,

  COALESCE(
    NULLIF(btrim(max(gl.fluor_tag_style)), ''),
    NULLIF(btrim(max(v5.fluor_tag_style)), '')
  ) AS tx_gt_fluortag,

  COALESCE(
    NULLIF(btrim(max(gl.fluor_organelle_style)), ''),
    NULLIF(btrim(max(v5.fluor_organelle_style)), '')
  ) AS tx_gt_fluororganelle,

  ch.n_channels_total,
  ch.n_channels_kept,
  ch.kept_channels_key
FROM public.v11_roi_treatment_table_display t
LEFT JOIN public.imaging_roi_annotations ira ON ira.id = t.roi_id
LEFT JOIN public.imaging_clutch_memberships m ON m.slot_id = ira.slot_id
LEFT JOIN public.treated_clutches_v11 tc ON tc.id = m.treated_clutch_id
LEFT JOIN public.treatments tr ON tr.id = tc.treatment_id
LEFT JOIN public.v_imaging_roi_channel_qc_rollup_v2 ch ON ch.roi_id = t.roi_id
LEFT JOIN public.clutches c ON c.clutch_code = t.clutch_code
LEFT JOIN public.v11_genotype_label_star gl ON gl.genotype_v11_id = c.genotype_v11_id
LEFT JOIN public.v11_v5_roi_label_fallback v5 ON v5.roi_id = t.roi_id
GROUP BY
  t.experiment_date, t.experiment_name, t.plate_note, t.slot_note, t.slot_orientation,
  t.roi_id, t.roi_code, t.roi_index_within_slot, t.roi_note_anatomy, t.roi_path,
  ira.n_tiffs, t.clutch_code,
  ch.n_channels_total, ch.n_channels_kept, ch.kept_channels_key;

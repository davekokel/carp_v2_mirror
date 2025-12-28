CREATE OR REPLACE VIEW public.v11_v5_roi_treatment_label_fallback AS
WITH base AS (
  SELECT
    a.id AS roi_id,
    a.roi_path,
    NULLIF(btrim(a.v5_treatment_plasmid_base_codes), '') AS plasmids_raw,
    NULLIF(btrim(a.v5_treatment_rna_base_codes), '') AS rnas_raw,
    (NULLIF(btrim(a.v5_treatment_plasmid_base_codes), '') IS NOT NULL) AS has_plasmid,
    (NULLIF(btrim(a.v5_treatment_rna_base_codes), '') IS NOT NULL) AS has_rna
  FROM public.imaging_roi_annotations a
),
tokens_raw AS (
  SELECT
    b.roi_id,
    lower(btrim(tok.tok)) AS tok,
    'plasmid'::text AS src
  FROM base b
  CROSS JOIN LATERAL regexp_split_to_table(COALESCE(b.plasmids_raw, ''), '[,;|[:space:]]+') tok(tok)
  WHERE NULLIF(btrim(tok.tok), '') IS NOT NULL

  UNION ALL

  SELECT
    b.roi_id,
    lower(btrim(tok.tok)) AS tok,
    'rna'::text AS src
  FROM base b
  CROSS JOIN LATERAL regexp_split_to_table(COALESCE(b.rnas_raw, ''), '[,;|[:space:]]+') tok(tok)
  WHERE NULLIF(btrim(tok.tok), '') IS NOT NULL
),
tokens_norm AS (
  SELECT
    tr.roi_id,
    tr.src,
    CASE
      WHEN regexp_match(regexp_replace(tr.tok, '[^a-z0-9\-]+', '', 'g'), '^([a-z]+)-?0*([0-9]+)$') IS NOT NULL
        THEN format(
          '%s-%s',
          (regexp_match(regexp_replace(tr.tok, '[^a-z0-9\-]+', '', 'g'), '^([a-z]+)-?0*([0-9]+)$'))[1],
          ((regexp_match(regexp_replace(tr.tok, '[^a-z0-9\-]+', '', 'g'), '^([a-z]+)-?0*([0-9]+)$'))[2])::int
        )
      ELSE regexp_replace(tr.tok, '[^a-z0-9\-]+', '', 'g')
    END AS base_code_norm
  FROM tokens_raw tr
),
t_constructs AS (
  SELECT DISTINCT
    tn.roi_id,
    tn.src,
    tn.base_code_norm,
    c.id AS construct_id
  FROM tokens_norm tn
  JOIN public.constructs c
    ON lower(c.base_code) = tn.base_code_norm
  WHERE NULLIF(btrim(tn.base_code_norm), '') IS NOT NULL
),
fusion_bits AS (
  SELECT
    tc.roi_id,
    COALESCE(fl.nickname, fl.display_name, fl.code) AS fluor_label,
    COALESCE(tg.nickname, tg.display_name, tg.code) AS tag_label,
    tg.localization,
    f.tag_pos,
    CASE
      WHEN tg.id IS NULL THEN COALESCE(fl.nickname, fl.display_name, fl.code)
      ELSE format(
        '%s-%s(%s)',
        COALESCE(fl.nickname, fl.display_name, fl.code),
        COALESCE(tg.nickname, tg.display_name, tg.code),
        f.tag_pos
      )
    END AS fluor_tag_label,
    CASE
      WHEN tg.localization IS NULL OR tg.localization = '' THEN COALESCE(fl.nickname, fl.display_name, fl.code)
      ELSE format('%s-%s', COALESCE(fl.nickname, fl.display_name, fl.code), tg.localization)
    END AS organelle_fluor_label
  FROM t_constructs tc
  JOIN public.construct_fusions cf ON cf.construct_id = tc.construct_id
  JOIN public.fusions f ON f.id = cf.fusion_id
  JOIN public.fluors fl ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg ON tg.id = f.tag_id
),
fluor_tag_rollup AS (
  SELECT
    fb.roi_id,
    string_agg(DISTINCT fb.fluor_tag_label, '; ' ORDER BY fb.fluor_tag_label) AS all_fluor_tag_rollup,
    string_agg(DISTINCT fb.organelle_fluor_label, '; ' ORDER BY fb.organelle_fluor_label) AS all_organelle_fluor_rollup
  FROM fusion_bits fb
  GROUP BY fb.roi_id
)
SELECT
  b.roi_id,
  b.roi_path,
  NULLIF(btrim(ft.all_fluor_tag_rollup), '') AS fluor_tag_style,
  NULLIF(btrim(ft.all_organelle_fluor_rollup), '') AS fluor_organelle_style,
  b.has_plasmid,
  b.has_rna
FROM base b
LEFT JOIN fluor_tag_rollup ft ON ft.roi_id = b.roi_id;

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
  string_agg(DISTINCT COALESCE(t.treated_clutch_code, tc.treated_clutch_code), '; ' ORDER BY (COALESCE(t.treated_clutch_code, tc.treated_clutch_code)))
    FILTER (WHERE COALESCE(t.treated_clutch_code, tc.treated_clutch_code) IS NOT NULL) AS treated_clutch_codes,
  string_agg(DISTINCT COALESCE(t.treatment_code, tr.treat_code), '; ' ORDER BY (COALESCE(t.treatment_code, tr.treat_code)))
    FILTER (WHERE COALESCE(t.treatment_code, tr.treat_code) IS NOT NULL) AS treatment_codes,
  string_agg(DISTINCT t.plasmids_display, '; ' ORDER BY t.plasmids_display) FILTER (WHERE t.plasmids_display IS NOT NULL) AS plasmids_display,
  string_agg(DISTINCT t.rnas_display, '; ' ORDER BY t.rnas_display) FILTER (WHERE t.rnas_display IS NOT NULL) AS rnas_display,
  string_agg(DISTINCT t.dyes_display, '; ' ORDER BY t.dyes_display) FILTER (WHERE t.dyes_display IS NOT NULL) AS dyes_display,

  COALESCE(
    NULLIF(btrim(max(gl.tg_style_canon)), ''),
    NULLIF(btrim(max(v5g.tg_style_canon)), '')
  ) AS tx_gt_tg,

  CASE
    WHEN COALESCE(NULLIF(btrim(max(v5t.fluor_tag_style)), ''), NULL) IS NULL
      AND COALESCE(NULLIF(btrim(max(gl.fluor_tag_style)), ''), NULLIF(btrim(max(v5g.fluor_tag_style)), '')) IS NULL
      THEN NULL
    WHEN COALESCE(NULLIF(btrim(max(v5t.fluor_tag_style)), ''), NULL) IS NULL
      THEN COALESCE(NULLIF(btrim(max(gl.fluor_tag_style)), ''), NULLIF(btrim(max(v5g.fluor_tag_style)), ''))
    WHEN COALESCE(NULLIF(btrim(max(gl.fluor_tag_style)), ''), NULLIF(btrim(max(v5g.fluor_tag_style)), '')) IS NULL
      THEN
        CASE
          WHEN bool_or(v5t.has_rna) AND NOT bool_or(v5t.has_plasmid) THEN 'rna(' || NULLIF(btrim(max(v5t.fluor_tag_style)), '') || ')'
          WHEN bool_or(v5t.has_plasmid) AND NOT bool_or(v5t.has_rna) THEN 'plasmid(' || NULLIF(btrim(max(v5t.fluor_tag_style)), '') || ')'
          ELSE NULLIF(btrim(max(v5t.fluor_tag_style)), '')
        END
    ELSE
      (
        CASE
          WHEN bool_or(v5t.has_rna) AND NOT bool_or(v5t.has_plasmid) THEN 'rna(' || NULLIF(btrim(max(v5t.fluor_tag_style)), '') || ')'
          WHEN bool_or(v5t.has_plasmid) AND NOT bool_or(v5t.has_rna) THEN 'plasmid(' || NULLIF(btrim(max(v5t.fluor_tag_style)), '') || ')'
          ELSE NULLIF(btrim(max(v5t.fluor_tag_style)), '')
        END
      ) || ' > ' || COALESCE(NULLIF(btrim(max(gl.fluor_tag_style)), ''), NULLIF(btrim(max(v5g.fluor_tag_style)), ''))
  END AS tx_gt_fluortag,

  CASE
    WHEN COALESCE(NULLIF(btrim(max(v5t.fluor_organelle_style)), ''), NULL) IS NULL
      AND COALESCE(NULLIF(btrim(max(gl.fluor_organelle_style)), ''), NULLIF(btrim(max(v5g.fluor_organelle_style)), '')) IS NULL
      THEN NULL
    WHEN COALESCE(NULLIF(btrim(max(v5t.fluor_organelle_style)), ''), NULL) IS NULL
      THEN COALESCE(NULLIF(btrim(max(gl.fluor_organelle_style)), ''), NULLIF(btrim(max(v5g.fluor_organelle_style)), ''))
    WHEN COALESCE(NULLIF(btrim(max(gl.fluor_organelle_style)), ''), NULLIF(btrim(max(v5g.fluor_organelle_style)), '')) IS NULL
      THEN
        CASE
          WHEN bool_or(v5t.has_rna) AND NOT bool_or(v5t.has_plasmid) THEN 'rna(' || NULLIF(btrim(max(v5t.fluor_organelle_style)), '') || ')'
          WHEN bool_or(v5t.has_plasmid) AND NOT bool_or(v5t.has_rna) THEN 'plasmid(' || NULLIF(btrim(max(v5t.fluor_organelle_style)), '') || ')'
          ELSE NULLIF(btrim(max(v5t.fluor_organelle_style)), '')
        END
    ELSE
      (
        CASE
          WHEN bool_or(v5t.has_rna) AND NOT bool_or(v5t.has_plasmid) THEN 'rna(' || NULLIF(btrim(max(v5t.fluor_organelle_style)), '') || ')'
          WHEN bool_or(v5t.has_plasmid) AND NOT bool_or(v5t.has_rna) THEN 'plasmid(' || NULLIF(btrim(max(v5t.fluor_organelle_style)), '') || ')'
          ELSE NULLIF(btrim(max(v5t.fluor_organelle_style)), '')
        END
      ) || ' > ' || COALESCE(NULLIF(btrim(max(gl.fluor_organelle_style)), ''), NULLIF(btrim(max(v5g.fluor_organelle_style)), ''))
  END AS tx_gt_fluororganelle,

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
LEFT JOIN public.v11_v5_roi_label_fallback v5g ON v5g.roi_id = t.roi_id
LEFT JOIN public.v11_v5_roi_treatment_label_fallback v5t ON v5t.roi_id = t.roi_id

GROUP BY
  t.experiment_date, t.experiment_name, t.plate_note, t.slot_note, t.slot_orientation,
  t.roi_id, t.roi_code, t.roi_index_within_slot, t.roi_note_anatomy, t.roi_path,
  ira.n_tiffs, t.clutch_code,
  ch.n_channels_total, ch.n_channels_kept, ch.kept_channels_key;

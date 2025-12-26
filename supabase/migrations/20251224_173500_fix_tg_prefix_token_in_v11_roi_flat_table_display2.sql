BEGIN;

DROP VIEW IF EXISTS public.v11_roi_flat_table_display2;

CREATE VIEW public.v11_roi_flat_table_display2 AS
WITH jct1 AS (
  SELECT c.clutch_code, count(*) AS n_join
  FROM public.join_clutch_treatments j
  JOIN public.clutches c ON c.id = j.clutch_id
  GROUP BY 1
),
one_jct AS (
  SELECT c.clutch_code, j.treatment_id
  FROM public.join_clutch_treatments j
  JOIN public.clutches c ON c.id = j.clutch_id
  JOIN jct1 n ON n.clutch_code = c.clutch_code AND n.n_join = 1
),
treat_parts AS (
  SELECT
    oj.clutch_code,
    lower(coalesce(tmc.delivery_form,'')) AS delivery_form,

    -- TG-style: basecode only (no extra tg(...) wrapper)
    lower(coalesce(cons.base_code,'')) AS tok_tg,

    -- Fluor-tag: fluor-tag(tagpos)
    CASE
      WHEN coalesce(btrim(fl.nickname),'') <> '' AND coalesce(btrim(tg.nickname),'') <> '' AND coalesce(btrim(f.tag_pos),'') <> ''
        THEN (fl.nickname || '-' || tg.nickname || '(' || f.tag_pos || ')')
      WHEN coalesce(btrim(fl.nickname),'') <> '' AND coalesce(btrim(tg.nickname),'') <> ''
        THEN (fl.nickname || '-' || tg.nickname)
      WHEN coalesce(btrim(fl.nickname),'') <> ''
        THEN fl.nickname
      ELSE NULL
    END AS tok_fluortag,

    -- Fluor-organelle: fluor-organelle
    CASE
      WHEN coalesce(btrim(fl.nickname),'') <> '' AND coalesce(btrim(tg.localization),'') <> ''
        THEN (fl.nickname || '-' || tg.localization)
      WHEN coalesce(btrim(fl.nickname),'') <> ''
        THEN fl.nickname
      ELSE NULL
    END AS tok_fluororganelle

  FROM one_jct oj
  JOIN public.treatment_mixes tm ON tm.treatment_id = oj.treatment_id
  JOIN public.treatment_mix_constructs tmc ON tmc.mix_id = tm.id
  JOIN public.constructs cons ON cons.id = tmc.construct_id

  LEFT JOIN public.construct_fusions cf ON cf.construct_id = cons.id
  LEFT JOIN public.fusions f            ON f.id = cf.fusion_id
  LEFT JOIN public.fluors fl            ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg              ON tg.id = f.tag_id

  WHERE coalesce(btrim(cons.base_code), '') <> ''
    AND lower(coalesce(tmc.delivery_form,'')) IN ('plasmid','rna','crispr')
),
treat_typed AS (
  SELECT
    clutch_code,

    string_agg(
      DISTINCT (delivery_form || '(' || tok_tg || ')'),
      '|' ORDER BY (delivery_form || '(' || tok_tg || ')')
    ) AS treat_tg_typed,

    string_agg(
      DISTINCT (delivery_form || '(' || tok_fluortag || ')'),
      '|' ORDER BY (delivery_form || '(' || tok_fluortag || ')')
    ) FILTER (WHERE coalesce(btrim(tok_fluortag),'') <> '') AS treat_fluortag_typed,

    string_agg(
      DISTINCT (delivery_form || '(' || tok_fluororganelle || ')'),
      '|' ORDER BY (delivery_form || '(' || tok_fluororganelle || ')')
    ) FILTER (WHERE coalesce(btrim(tok_fluororganelle),'') <> '') AS treat_fluororganelle_typed

  FROM treat_parts
  GROUP BY 1
)
SELECT
  r.experiment_date,
  r.experiment_name,
  r.plate_note,
  r.slot_note,
  r.slot_orientation,
  r.roi_id,
  r.roi_code,
  r.roi_index_within_slot,
  r.roi_note_anatomy,
  r.roi_path,
  r.n_tiffs,
  r.clutch_code,
  r.treated_clutch_codes,
  r.treatment_codes,

  CASE
    WHEN coalesce(btrim(r.tx_gt_tg),'') <> '' AND r.tx_gt_tg LIKE '% > %' THEN r.tx_gt_tg
    WHEN coalesce(btrim(tt.treat_tg_typed),'') <> '' AND coalesce(btrim(r.tx_gt_tg),'') <> '' THEN tt.treat_tg_typed || ' > ' || r.tx_gt_tg
    WHEN coalesce(btrim(tt.treat_tg_typed),'') <> '' AND coalesce(btrim(r.tx_gt_tg),'') = '' THEN tt.treat_tg_typed || CASE WHEN coalesce(btrim(c.genetic_background),'') <> '' THEN ' > ' || c.genetic_background ELSE '' END
    ELSE coalesce(r.tx_gt_tg,'')
  END AS tx_gt_tg,

  CASE
    WHEN coalesce(btrim(r.tx_gt_fluortag),'') <> '' AND r.tx_gt_fluortag LIKE '% > %' THEN r.tx_gt_fluortag
    WHEN coalesce(btrim(tt.treat_fluortag_typed),'') <> '' AND coalesce(btrim(r.tx_gt_fluortag),'') <> '' THEN tt.treat_fluortag_typed || ' > ' || r.tx_gt_fluortag
    WHEN coalesce(btrim(tt.treat_fluortag_typed),'') <> '' AND coalesce(btrim(r.tx_gt_fluortag),'') = '' THEN tt.treat_fluortag_typed || CASE WHEN coalesce(btrim(c.genetic_background),'') <> '' THEN ' > ' || c.genetic_background ELSE '' END
    ELSE coalesce(r.tx_gt_fluortag,'')
  END AS tx_gt_fluortag,

  CASE
    WHEN coalesce(btrim(r.tx_gt_fluororganelle),'') <> '' AND r.tx_gt_fluororganelle LIKE '% > %' THEN r.tx_gt_fluororganelle
    WHEN coalesce(btrim(tt.treat_fluororganelle_typed),'') <> '' AND coalesce(btrim(r.tx_gt_fluororganelle),'') <> '' THEN tt.treat_fluororganelle_typed || ' > ' || r.tx_gt_fluororganelle
    WHEN coalesce(btrim(tt.treat_fluororganelle_typed),'') <> '' AND coalesce(btrim(r.tx_gt_fluororganelle),'') = '' THEN tt.treat_fluororganelle_typed || CASE WHEN coalesce(btrim(c.genetic_background),'') <> '' THEN ' > ' || c.genetic_background ELSE '' END
    ELSE coalesce(r.tx_gt_fluororganelle,'')
  END AS tx_gt_fluororganelle,

  r.plasmids_display,
  r.rnas_display,
  r.dyes_display,
  r.n_channels_total,
  r.n_channels_kept,
  r.kept_channels_key
FROM public.v11_roi_flat_table_display r
LEFT JOIN public.clutches c ON c.clutch_code = r.clutch_code
LEFT JOIN treat_typed tt ON tt.clutch_code = r.clutch_code;

COMMIT;

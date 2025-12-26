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
mix_parts AS (
  SELECT
    oj.clutch_code,
    lower(coalesce(btrim(tmc.delivery_form), '')) AS delivery_form,
    lower(coalesce(btrim(cons.base_code), ''))     AS construct_base_code,
    lower(coalesce(btrim(fl.nickname), ''))        AS fluor_nickname,
    lower(coalesce(btrim(tg.nickname), ''))        AS tag_nickname,
    lower(coalesce(btrim(f.tag_pos), ''))          AS tag_pos,
    lower(coalesce(btrim(tg.localization), ''))    AS localization
  FROM one_jct oj
  JOIN public.treatment_mixes tm
    ON tm.treatment_id = oj.treatment_id
  LEFT JOIN public.treatment_mix_constructs tmc
    ON tmc.mix_id = tm.id
  LEFT JOIN public.constructs cons
    ON cons.id = tmc.construct_id
  LEFT JOIN public.construct_fusions cf
    ON cf.construct_id = cons.id
  LEFT JOIN public.fusions f
    ON f.id = cf.fusion_id
  LEFT JOIN public.fluors fl
    ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg
    ON tg.id = f.tag_id
),
treat_tokens AS (
  SELECT
    clutch_code,

    string_agg(
      DISTINCT (delivery_form || '(' || construct_base_code || ')'),
      '|' ORDER BY (delivery_form || '(' || construct_base_code || ')')
    ) FILTER (
      WHERE delivery_form IN ('plasmid','rna','crispr')
        AND construct_base_code <> ''
    ) AS treat_tg_typed,

    string_agg(
      DISTINCT (
        delivery_form || '(' ||
        CASE
          WHEN fluor_nickname <> '' AND tag_nickname <> '' AND tag_pos <> '' THEN fluor_nickname || '-' || tag_nickname || '(' || tag_pos || ')'
          WHEN fluor_nickname <> '' AND tag_nickname <> '' AND tag_pos = ''  THEN fluor_nickname || '-' || tag_nickname
          WHEN fluor_nickname <> '' AND tag_nickname = ''                   THEN fluor_nickname
          ELSE ''
        END
        || ')'
      ),
      '|' ORDER BY (
        delivery_form || '(' ||
        CASE
          WHEN fluor_nickname <> '' AND tag_nickname <> '' AND tag_pos <> '' THEN fluor_nickname || '-' || tag_nickname || '(' || tag_pos || ')'
          WHEN fluor_nickname <> '' AND tag_nickname <> '' AND tag_pos = ''  THEN fluor_nickname || '-' || tag_nickname
          WHEN fluor_nickname <> '' AND tag_nickname = ''                   THEN fluor_nickname
          ELSE ''
        END
        || ')'
      )
    ) FILTER (
      WHERE delivery_form IN ('plasmid','rna','crispr')
        AND fluor_nickname <> ''
    ) AS treat_fluortag_typed,

    string_agg(
      DISTINCT (
        delivery_form || '(' ||
        CASE
          WHEN localization <> '' THEN fluor_nickname || '-' || localization
          ELSE fluor_nickname
        END
        || ')'
      ),
      '|' ORDER BY (
        delivery_form || '(' ||
        CASE
          WHEN localization <> '' THEN fluor_nickname || '-' || localization
          ELSE fluor_nickname
        END
        || ')'
      )
    ) FILTER (
      WHERE delivery_form IN ('plasmid','rna','crispr')
        AND fluor_nickname <> ''
    ) AS treat_fluororganelle_typed

  FROM mix_parts
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
LEFT JOIN treat_tokens tt ON tt.clutch_code = r.clutch_code;

COMMIT;

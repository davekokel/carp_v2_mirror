BEGIN;

CREATE OR REPLACE VIEW public.v11_clutch_label_star AS
WITH geno_markers AS (
  SELECT
    g.id                    AS genotype_id,
    vco.fusion_pretty,
    vco.organelle_fluors
  FROM public.genotypes_v11 g
  LEFT JOIN public.join_genotype_constructs_v11 j
    ON j.genotype_id = g.id
  LEFT JOIN public.constructs c
    ON c.id = j.construct_id
  LEFT JOIN public.v_constructs_overview vco
    ON vco.construct_code = c.construct_code
),
geno_agg AS (
  SELECT
    genotype_id,
    string_agg(DISTINCT fusion_pretty, '; ' ORDER BY fusion_pretty)       AS genotype_fluortag_style,
    string_agg(DISTINCT organelle_fluors, '; ' ORDER BY organelle_fluors) AS genotype_fluororganelle_style
  FROM geno_markers
  GROUP BY genotype_id
),

base_clutches AS (
  SELECT
    c.id::uuid                AS clutch_id,
    c.clutch_code,
    c.clutch_date,
    c.genotype_v11_id::uuid   AS genotype_v11_id,
    g.id::uuid                AS genotype_id,
    g.genotype_code,
    g.genotype_basecodes,
    g.genotype_pretty,
    ga.genotype_fluortag_style,
    ga.genotype_fluororganelle_style
  FROM public.clutches c
  LEFT JOIN public.genotypes_v11 g
    ON g.id = c.genotype_v11_id
  LEFT JOIN geno_agg ga
    ON ga.genotype_id = g.id
),

treated AS (
  SELECT
    tc.id::uuid         AS treated_clutch_id,
    tc.clutch_id::uuid  AS clutch_id,
    tc.treated_clutch_code,
    t.treat_code        AS treatment_code,
    t.treat_text
  FROM public.treated_clutches_v11 tc
  LEFT JOIN public.treatments t
    ON t.id = tc.treatment_id
),

selection_events AS (
  SELECT
    cse.id::uuid            AS selection_event_id,
    cse.selection_label,
    cse.clutch_id::uuid     AS clutch_id,
    cse.treated_clutch_id::uuid AS treated_clutch_id
  FROM public.clutch_selection_events_v11 cse
),

treatment_labels AS (
  SELECT
    treated_clutch_id,
    string_agg(DISTINCT treatment_label_tg_style, ' || ' ORDER BY treatment_label_tg_style)           AS treatment_label_tg_style,
    string_agg(DISTINCT treatment_label_fluortag_style, ' || ' ORDER BY treatment_label_fluortag_style) AS treatment_label_fluortag_style,
    string_agg(DISTINCT treatment_label_fluororganelle_style, ' || ' ORDER BY treatment_label_fluororganelle_style) AS treatment_label_fluororganelle_style
  FROM public.v11_treated_clutch_genotype_star_labels
  GROUP BY treated_clutch_id
),

clutch_rows AS (
  SELECT
    'clutch'                     AS clutch_kind,
    bc.clutch_id,
    NULL::uuid                   AS treated_clutch_id,
    NULL::uuid                   AS selection_event_id,
    bc.clutch_code,
    bc.clutch_date,
    NULL::text                   AS treated_clutch_code,
    NULL::text                   AS treatment_code,
    NULL::text                   AS treat_text,
    NULL::text                   AS selection_label,
    bc.genotype_v11_id,
    bc.genotype_code,
    bc.genotype_basecodes,
    bc.genotype_pretty,
    bc.genotype_pretty           AS genotype_tg_style,
    bc.genotype_fluortag_style,
    bc.genotype_fluororganelle_style,
    bc.genotype_pretty           AS label_tg_style,
    bc.genotype_fluortag_style   AS label_fluortag_style,
    bc.genotype_fluororganelle_style AS label_fluororganelle_style
  FROM base_clutches bc
),

treated_rows AS (
  SELECT
    'treated_clutch'             AS clutch_kind,
    bc.clutch_id,
    tr.treated_clutch_id,
    NULL::uuid                   AS selection_event_id,
    bc.clutch_code,
    bc.clutch_date,
    tr.treated_clutch_code,
    tr.treatment_code,
    tr.treat_text,
    NULL::text                   AS selection_label,
    bc.genotype_v11_id,
    bc.genotype_code,
    bc.genotype_basecodes,
    bc.genotype_pretty,
    bc.genotype_pretty           AS genotype_tg_style,
    bc.genotype_fluortag_style,
    bc.genotype_fluororganelle_style,
    la.treatment_label_tg_style,
    la.treatment_label_fluortag_style,
    la.treatment_label_fluororganelle_style
  FROM base_clutches bc
  JOIN treated tr
    ON tr.clutch_id = bc.clutch_id
  LEFT JOIN treatment_labels la
    ON la.treated_clutch_id = tr.treated_clutch_id
),

selection_rows AS (
  SELECT
    'selection'                  AS clutch_kind,
    bc.clutch_id,
    tr.treated_clutch_id,
    se.selection_event_id,
    bc.clutch_code,
    bc.clutch_date,
    tr.treated_clutch_code,
    tr.treatment_code,
    tr.treat_text,
    se.selection_label,
    bc.genotype_v11_id,
    bc.genotype_code,
    bc.genotype_basecodes,
    bc.genotype_pretty,
    bc.genotype_pretty           AS genotype_tg_style,
    bc.genotype_fluortag_style,
    bc.genotype_fluororganelle_style,
    la.treatment_label_tg_style,
    la.treatment_label_fluortag_style,
    la.treatment_label_fluororganelle_style
  FROM base_clutches bc
  LEFT JOIN treated tr
    ON tr.clutch_id = bc.clutch_id
  JOIN selection_events se
    ON se.clutch_id = bc.clutch_id
   AND (tr.treated_clutch_id IS NULL OR se.treated_clutch_id = tr.treated_clutch_id)
  LEFT JOIN treatment_labels la
    ON la.treated_clutch_id = tr.treated_clutch_id
)

SELECT
  clutch_kind,
  clutch_id,
  treated_clutch_id,
  selection_event_id,
  clutch_code,
  clutch_date,
  treated_clutch_code,
  treatment_code,
  treat_text,
  selection_label,
  genotype_v11_id,
  genotype_code,
  genotype_basecodes,
  genotype_pretty,
  genotype_tg_style,
  genotype_fluortag_style,
  genotype_fluororganelle_style,
  label_tg_style,
  label_fluortag_style,
  label_fluororganelle_style
FROM clutch_rows

UNION ALL

SELECT
  clutch_kind,
  clutch_id,
  treated_clutch_id,
  selection_event_id,
  clutch_code,
  clutch_date,
  treated_clutch_code,
  treatment_code,
  treat_text,
  selection_label,
  genotype_v11_id,
  genotype_code,
  genotype_basecodes,
  genotype_pretty,
  genotype_tg_style,
  genotype_fluortag_style,
  genotype_fluororganelle_style,
  treatment_label_tg_style        AS label_tg_style,
  treatment_label_fluortag_style  AS label_fluortag_style,
  treatment_label_fluororganelle_style AS label_fluororganelle_style
FROM treated_rows

UNION ALL

SELECT
  clutch_kind,
  clutch_id,
  treated_clutch_id,
  selection_event_id,
  clutch_code,
  clutch_date,
  treated_clutch_code,
  treatment_code,
  treat_text,
  selection_label,
  genotype_v11_id,
  genotype_code,
  genotype_basecodes,
  genotype_pretty,
  genotype_tg_style,
  genotype_fluortag_style,
  genotype_fluororganelle_style,
  treatment_label_tg_style        AS label_tg_style,
  treatment_label_fluortag_style  AS label_fluortag_style,
  treatment_label_fluororganelle_style AS label_fluororganelle_style
FROM selection_rows;

COMMIT;

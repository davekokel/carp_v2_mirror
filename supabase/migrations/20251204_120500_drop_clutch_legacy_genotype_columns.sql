BEGIN;

-- 1) Rewrite v11_clutch_label_star so it no longer depends on clutches.legacy_genotype_*.
--    This keeps the same column list/shape as the original view so downstream views
--    (imaging, selections, etc.) continue to work unchanged.

CREATE OR REPLACE VIEW public.v11_clutch_label_star AS
WITH geno_markers AS (
  SELECT
    g.id                AS genotype_id,
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
    gm.genotype_id,
    string_agg(DISTINCT gm.fusion_pretty,    '; ' ORDER BY gm.fusion_pretty)    AS genotype_fluortag_style,
    string_agg(DISTINCT gm.organelle_fluors, '; ' ORDER BY gm.organelle_fluors) AS genotype_fluororganelle_style
  FROM geno_markers gm
  GROUP BY gm.genotype_id
),
base_clutches AS (
  SELECT
    c.id                     AS clutch_id,
    c.clutch_code,
    c.clutch_date,
    c.genotype_v11_id,
    g.id                     AS genotype_id,
    g.genotype_code,
    -- v11-only: do NOT fall back to legacy_genotype_* on clutches
    g.genotype_basecodes     AS genotype_basecodes,
    g.genotype_pretty        AS genotype_pretty,
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
    tc.id           AS treated_clutch_id,
    tc.clutch_id,
    tc.treated_clutch_code,
    t.treat_code    AS treatment_code,
    t.treat_text
  FROM public.treated_clutches_v11 tc
  LEFT JOIN public.treatments t
    ON t.id = tc.treatment_id
),
selection_events AS (
  SELECT
    cse.id          AS selection_event_id,
    cse.selection_label,
    cse.clutch_id,
    cse.treated_clutch_id
  FROM public.clutch_selection_events_v11 cse
),
treatment_labels AS (
  SELECT
    tcl.treated_clutch_id,
    string_agg(DISTINCT tcl.treatment_label_tg_style,          ' || ' ORDER BY tcl.treatment_label_tg_style)          AS treatment_label_tg_style,
    string_agg(DISTINCT tcl.treatment_label_fluortag_style,    ' || ' ORDER BY tcl.treatment_label_fluortag_style)    AS treatment_label_fluortag_style,
    string_agg(DISTINCT tcl.treatment_label_fluororganelle_style, ' || ' ORDER BY tcl.treatment_label_fluororganelle_style) AS treatment_label_fluororganelle_style
  FROM public.v11_treated_clutch_genotype_star_labels tcl
  GROUP BY tcl.treated_clutch_id
),
clutch_rows AS (
  SELECT
    'clutch'::text           AS clutch_kind,
    bc.clutch_id,
    NULL::uuid               AS treated_clutch_id,
    NULL::uuid               AS selection_event_id,
    bc.clutch_code,
    bc.clutch_date,
    NULL::text               AS treated_clutch_code,
    NULL::text               AS treatment_code,
    NULL::text               AS treat_text,
    NULL::text               AS selection_label,
    bc.genotype_v11_id,
    bc.genotype_code,
    bc.genotype_basecodes,
    bc.genotype_pretty,
    bc.genotype_pretty       AS genotype_tg_style,
    bc.genotype_fluortag_style,
    bc.genotype_fluororganelle_style,
    bc.genotype_pretty       AS label_tg_style,
    bc.genotype_fluortag_style       AS label_fluortag_style,
    bc.genotype_fluororganelle_style AS label_fluororganelle_style
  FROM base_clutches bc
),
treated_rows AS (
  SELECT
    'treated_clutch'::text    AS clutch_kind,
    bc.clutch_id,
    tr.treated_clutch_id,
    NULL::uuid                AS selection_event_id,
    bc.clutch_code,
    bc.clutch_date,
    tr.treated_clutch_code,
    tr.treatment_code,
    tr.treat_text,
    NULL::text                AS selection_label,
    bc.genotype_v11_id,
    bc.genotype_code,
    bc.genotype_basecodes,
    bc.genotype_pretty,
    bc.genotype_pretty        AS genotype_tg_style,
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
    'selection'::text         AS clutch_kind,
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
    bc.genotype_pretty        AS genotype_tg_style,
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
  cr.clutch_kind,
  cr.clutch_id,
  cr.treated_clutch_id,
  cr.selection_event_id,
  cr.clutch_code,
  cr.clutch_date,
  cr.treated_clutch_code,
  cr.treatment_code,
  cr.treat_text,
  cr.selection_label,
  cr.genotype_v11_id,
  cr.genotype_code,
  cr.genotype_basecodes,
  cr.genotype_pretty,
  cr.genotype_tg_style,
  cr.genotype_fluortag_style,
  cr.genotype_fluororganelle_style,
  cr.label_tg_style,
  cr.label_fluortag_style,
  cr.label_fluororganelle_style
FROM clutch_rows cr
UNION ALL
SELECT
  tr.clutch_kind,
  tr.clutch_id,
  tr.treated_clutch_id,
  tr.selection_event_id,
  tr.clutch_code,
  tr.clutch_date,
  tr.treated_clutch_code,
  tr.treatment_code,
  tr.treat_text,
  tr.selection_label,
  tr.genotype_v11_id,
  tr.genotype_code,
  tr.genotype_basecodes,
  tr.genotype_pretty,
  tr.genotype_tg_style,
  tr.genotype_fluortag_style,
  tr.genotype_fluororganelle_style,
  tr.treatment_label_tg_style       AS label_tg_style,
  tr.treatment_label_fluortag_style AS label_fluortag_style,
  tr.treatment_label_fluororganelle_style AS label_fluororganelle_style
FROM treated_rows tr
UNION ALL
SELECT
  sr.clutch_kind,
  sr.clutch_id,
  sr.treated_clutch_id,
  sr.selection_event_id,
  sr.clutch_code,
  sr.clutch_date,
  sr.treated_clutch_code,
  sr.treatment_code,
  sr.treat_text,
  sr.selection_label,
  sr.genotype_v11_id,
  sr.genotype_code,
  sr.genotype_basecodes,
  sr.genotype_pretty,
  sr.genotype_tg_style,
  sr.genotype_fluortag_style,
  sr.genotype_fluororganelle_style,
  sr.treatment_label_tg_style       AS label_tg_style,
  sr.treatment_label_fluortag_style AS label_fluortag_style,
  sr.treatment_label_fluororganelle_style AS label_fluororganelle_style
FROM selection_rows sr;

-- 2) Now that the view no longer depends on legacy_genotype_* columns,
--    we can safely drop them from clutches.

ALTER TABLE public.clutches
  DROP COLUMN IF EXISTS legacy_genotype_cross_label,
  DROP COLUMN IF EXISTS legacy_genotype_base_codes,
  DROP COLUMN IF EXISTS legacy_genotype_allele_codes,
  DROP COLUMN IF EXISTS legacy_genotype_pretty,
  DROP COLUMN IF EXISTS legacy_observed_genotype_code;

COMMIT;

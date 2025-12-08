BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_treated_groups_flat;

CREATE VIEW public.v11_clutch_treated_groups_flat AS
WITH treated AS (
  SELECT
    tc.id::uuid                  AS treated_clutch_id,
    tc.treated_clutch_code,
    c.id::uuid                   AS clutch_id,
    c.clutch_code,
    c.clutch_date,

    g.genotype_basecodes::text   AS genotype_basecodes,
    g.genotype_pretty::text      AS genotype_pretty,

    t.treat_code                 AS treatment_code,
    COALESCE(ts.treat_basecodes, '')           AS treat_basecodes,
    COALESCE(ts.label_fluortag_style, '')      AS treat_fluortag_style,
    COALESCE(ts.label_fluororganelle_style, '') AS treat_organelle_style,

    -- what the UI will type into the wells
    tc.treated_clutch_code       AS assign_code
  FROM public.treated_clutches_v11 tc
  JOIN public.clutches c
    ON c.id = tc.clutch_id
  LEFT JOIN public.genotypes_v11 g
    ON g.id = c.genotype_v11_id
  LEFT JOIN public.treatments t
    ON t.id = tc.treatment_id
  LEFT JOIN public.v11_treatment_star ts
    -- ts.treatment_id is text, t.id is uuid
    ON ts.treatment_id = t.id::text
  WHERE c.clutch_date >= (current_date - INTERVAL '14 days')
    AND COALESCE(c.source_system, '') <> 'legacy_imaging'
),
untreated AS (
  SELECT
    NULL::uuid                    AS treated_clutch_id,
    NULL::text                    AS treated_clutch_code,
    c.id::uuid                    AS clutch_id,
    c.clutch_code,
    c.clutch_date,

    g.genotype_basecodes::text    AS genotype_basecodes,
    g.genotype_pretty::text       AS genotype_pretty,

    NULL::text                    AS treatment_code,
    ''::text                      AS treat_basecodes,
    ''::text                      AS treat_fluortag_style,
    ''::text                      AS treat_organelle_style,

    -- for untreated, assign using the parent clutch code
    c.clutch_code                 AS assign_code
  FROM public.clutches c
  LEFT JOIN public.genotypes_v11 g
    ON g.id = c.genotype_v11_id
  WHERE c.clutch_date >= (current_date - INTERVAL '14 days')
    AND COALESCE(c.source_system, '') <> 'legacy_imaging'
),
all_groups AS (
  SELECT * FROM treated
  UNION ALL
  SELECT * FROM untreated
)
SELECT
  treated_clutch_id::text,
  treated_clutch_code,
  clutch_id::text,
  clutch_code,
  clutch_date,
  genotype_pretty,
  genotype_basecodes,
  treatment_code,

  treat_basecodes,
  treat_fluortag_style,
  treat_organelle_style,

  CASE
    WHEN COALESCE(treat_basecodes, '') = '' THEN genotype_basecodes
    WHEN COALESCE(genotype_basecodes, '') = '' THEN treat_basecodes
    ELSE treat_basecodes || ' > ' || genotype_basecodes
  END AS marker_basecode_style,

  treat_fluortag_style  AS marker_fluortag_style,
  treat_organelle_style AS marker_organelle_style,

  assign_code
FROM all_groups
ORDER BY clutch_date DESC, assign_code;

COMMENT ON VIEW public.v11_clutch_treated_groups_flat IS
'Flat v11 imaging groups: treated clutches plus plain clutches, with genotype basecodes and marker styles. marker_basecode_style encodes treat_basecodes > genotype_basecodes; untreated rows show genotype_basecodes only.';

COMMIT;

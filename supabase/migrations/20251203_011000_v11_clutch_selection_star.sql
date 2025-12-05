BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_selection_star;

CREATE VIEW public.v11_clutch_selection_star AS
WITH base AS (
  SELECT
    se.id                 AS selection_event_id,
    se.clutch_id,
    se.treated_clutch_id,
    se.selection_kind,
    se.selection_label,
    se.notes,
    se.created_at,
    se.created_by
  FROM public.clutch_selection_events_v11 se
),
links AS (
  SELECT
    sg.selection_event_id,
    sg.clutch_genotype_id,
    sg.is_primary,
    sg.created_at  AS link_created_at,
    sg.created_by  AS link_created_by
  FROM public.clutch_selection_genotypes_v11 sg
)
SELECT
  b.selection_event_id,
  b.selection_kind,
  b.selection_label,
  b.notes,
  b.created_at              AS selection_created_at,
  b.created_by,

  c.id                      AS clutch_id,
  c.clutch_code,
  c.clutch_date,

  tc.id                     AS treated_clutch_id,
  tc.treated_clutch_code,
  t.treat_code              AS treatment_code,
  t.treat_text,

  links.clutch_genotype_id,
  cg.genotype_v11_id,
  gv.genotype_code,
  gv.genotype_basecodes,
  gv.genotype_pretty,
  links.is_primary
FROM base b
JOIN public.clutches c
  ON c.id = b.clutch_id
LEFT JOIN public.treated_clutches_v11 tc
  ON tc.id = b.treated_clutch_id
LEFT JOIN public.treatments t
  ON t.id = tc.treatment_id
LEFT JOIN links
  ON links.selection_event_id = b.selection_event_id
LEFT JOIN public.clutch_genotypes_v11 cg
  ON cg.id = links.clutch_genotype_id
LEFT JOIN public.genotypes_v11 gv
  ON gv.id = cg.genotype_v11_id
ORDER BY
  c.clutch_date DESC NULLS LAST,
  c.clutch_code,
  b.created_at,
  gv.genotype_code;

COMMENT ON VIEW public.v11_clutch_selection_star IS
'Selection-level rollup: one row per (selection_event × expected clutch genotype). A selection event belongs to a clutch and optionally a treated clutch. If a selection event links to multiple clutch_genotypes_v11, they appear as separate rows, with is_primary highlighting the primary genotype if set.';

COMMIT;

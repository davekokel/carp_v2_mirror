BEGIN;

DROP VIEW IF EXISTS public.v11_treatment_star;

CREATE VIEW public.v11_treatment_star AS
WITH mix_constructs AS (
  SELECT
    tm.treatment_id,
    tmc.construct_id
  FROM public.treatment_mixes tm
  JOIN public.treatment_mix_constructs tmc
    ON tmc.mix_id = tm.id
),
base_codes AS (
  SELECT
    mc.treatment_id,
    string_agg(
      DISTINCT c.construct_code,
      '; ' ORDER BY c.construct_code
    ) AS genotype_basecode_code
  FROM mix_constructs mc
  JOIN public.constructs c
    ON c.id = mc.construct_id
  GROUP BY mc.treatment_id
),
-- group construct codes by kind (plasmid / rna / crispr / etc.)
constructs_by_kind AS (
  SELECT
    mc.treatment_id,
    c.construct_kind,
    string_agg(
      DISTINCT c.construct_code,
      ', ' ORDER BY c.construct_code
    ) AS kind_codes
  FROM mix_constructs mc
  JOIN public.constructs c
    ON c.id = mc.construct_id
  GROUP BY mc.treatment_id, c.construct_kind
),
materials_by_kind AS (
  SELECT
    treatment_id,
    string_agg(
      format('%s(%s)', construct_kind, kind_codes),
      '; ' ORDER BY construct_kind
    ) AS materials_by_kind
  FROM constructs_by_kind
  GROUP BY treatment_id
),
fusion_bits AS (
  SELECT
    mc.treatment_id,
    fl.fluor_code,
    tg.tag_code,
    tg.localization,
    f.tag_pos,
    -- fluor::tag(tag_pos) or fluor::cytosol if no tag
    CASE
      WHEN tg.id IS NULL
        THEN format('%s::cytosol', fl.fluor_code)
      ELSE format('%s::%s(%s)', fl.fluor_code, tg.tag_code, f.tag_pos)
    END AS fluor_tag_label,
    -- organelle-fluor or cytosol-fluor if no localization
    format('%s-%s', COALESCE(NULLIF(tg.localization, ''), 'cytosol'), fl.fluor_code)
      AS organelle_fluor_label
  FROM mix_constructs mc
  JOIN public.construct_fusions cf
    ON cf.construct_id = mc.construct_id
  JOIN public.fusions f
    ON f.id = cf.fusion_id
  JOIN public.fluors fl
    ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg
    ON tg.id = f.tag_id
),
fluor_tag_rollup AS (
  SELECT
    treatment_id,
    string_agg(
      fluor_tag_label,
      '; ' ORDER BY fluor_tag_label
    ) AS all_fluor_tag_rollup
  FROM (
    SELECT DISTINCT treatment_id, fluor_tag_label
    FROM fusion_bits
  ) s
  GROUP BY treatment_id
),
organelle_fluor_rollup AS (
  SELECT
    treatment_id,
    string_agg(
      organelle_fluor_label,
      '; ' ORDER BY organelle_fluor_label
    ) AS all_organelle_fluor_rollup
  FROM (
    SELECT DISTINCT
      treatment_id,
      organelle_fluor_label
    FROM fusion_bits
  ) s
  GROUP BY treatment_id
)
SELECT
  t.id::text                                   AS treatment_id,
  t.treat_code                                 AS treatment_code,
  COALESCE(bc.genotype_basecode_code,'')       AS genotype_basecode_code,
  COALESCE(mk.materials_by_kind,'')            AS materials_by_kind,
  COALESCE(ft.all_fluor_tag_rollup,'')         AS all_fluor_tag_rollup,
  COALESCE(ofr.all_organelle_fluor_rollup,'')  AS all_organelle_fluor_rollup,
  t.kind_code,
  t.treat_text,
  t.created_at
FROM public.treatments t
LEFT JOIN base_codes             bc  ON bc.treatment_id  = t.id
LEFT JOIN materials_by_kind      mk  ON mk.treatment_id  = t.id
LEFT JOIN fluor_tag_rollup       ft  ON ft.treatment_id  = t.id
LEFT JOIN organelle_fluor_rollup ofr ON ofr.treatment_id = t.id;

COMMIT;

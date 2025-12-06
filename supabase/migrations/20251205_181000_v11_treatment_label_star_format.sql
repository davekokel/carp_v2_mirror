BEGIN;

CREATE OR REPLACE VIEW public.v11_treatment_label_star AS
WITH base AS (
  SELECT
    t.id::text       AS treatment_id,
    t.treat_code,
    t.kind_code,
    t.treatment_type,
    t.nickname,
    t.display_name,
    t.treat_text,
    t.notes,
    t.source_system,
    t.import_batch_id,
    t.created_at
  FROM public.treatments t
),
mix_counts AS (
  SELECT
    tm.treatment_id::text AS treatment_id,
    COUNT(*)::int         AS n_mixes
  FROM public.treatment_mixes tm
  GROUP BY tm.treatment_id
),
construct_counts AS (
  SELECT
    tm.treatment_id::text                 AS treatment_id,
    COUNT(DISTINCT tmc.construct_id)::int AS n_constructs
  FROM public.treatment_mixes tm
  JOIN public.treatment_mix_constructs tmc
    ON tmc.mix_id = tm.id
  GROUP BY tm.treatment_id
),
dye_counts AS (
  SELECT
    tm.treatment_id::text            AS treatment_id,
    COUNT(DISTINCT tmd.dye_id)::int  AS n_dyes
  FROM public.treatment_mixes tm
  JOIN public.treatment_mix_dyes tmd
    ON tmd.mix_id = tm.id
  GROUP BY tm.treatment_id
),
ingredient_kinds AS (
  -- subtypes: construct_kind (plasmid, rna, crispr, ...) + dye
  SELECT
    treatment_id::text AS treatment_id,
    string_agg(DISTINCT ingredient_kind, ', ' ORDER BY ingredient_kind) AS ingredient_kinds,
    COUNT(DISTINCT ingredient_kind)::int AS n_kinds
  FROM (
    SELECT
      tm.treatment_id,
      COALESCE(c.construct_kind, 'construct') AS ingredient_kind
    FROM public.treatment_mixes tm
    JOIN public.treatment_mix_constructs tmc
      ON tmc.mix_id = tm.id
    JOIN public.constructs c
      ON c.id = tmc.construct_id

    UNION

    SELECT
      tm.treatment_id,
      'dye'::text AS ingredient_kind
    FROM public.treatment_mixes tm
    JOIN public.treatment_mix_dyes tmd
      ON tmd.mix_id = tm.id
  ) x
  GROUP BY treatment_id
),
joined AS (
  SELECT
    b.treatment_id,
    b.treat_code,
    b.kind_code,
    b.treatment_type,
    b.nickname,
    b.display_name,
    b.treat_text,
    b.notes,
    b.source_system,
    b.import_batch_id,
    b.created_at,
    COALESCE(m.n_mixes, 0)        AS n_mixes,
    COALESCE(c.n_constructs, 0)   AS n_constructs,
    COALESCE(d.n_dyes, 0)         AS n_dyes,
    COALESCE(k.ingredient_kinds, '') AS ingredient_kinds,
    COALESCE(k.n_kinds, 0)        AS n_kinds,
    ts.genotype_basecode_code,
    ts.materials_by_kind,
    ts.all_fluor_tag_rollup,
    ts.all_organelle_fluor_rollup
  FROM base b
  LEFT JOIN mix_counts       m USING (treatment_id)
  LEFT JOIN construct_counts c USING (treatment_id)
  LEFT JOIN dye_counts       d USING (treatment_id)
  LEFT JOIN ingredient_kinds k USING (treatment_id)
  LEFT JOIN public.v11_treatment_star ts
    ON ts.treatment_id = b.treatment_id
)
SELECT
  j.treatment_id,
  j.treat_code,
  j.kind_code,
  j.treatment_type,
  j.nickname,
  j.display_name,
  j.treat_text,
  j.notes,
  j.source_system,
  j.import_batch_id,
  j.created_at,
  j.n_mixes,
  j.n_constructs,
  j.n_dyes,
  j.ingredient_kinds,
  j.n_kinds,
  j.genotype_basecode_code,
  j.materials_by_kind,
  j.all_fluor_tag_rollup       AS fluor_tag_style,
  j.all_organelle_fluor_rollup AS fluor_organelle_style,

  -- treatment_display WITHOUT braces, using materials_by_kind + optional "; dye"
  CASE
    WHEN COALESCE(j.materials_by_kind, '') = '' AND j.n_dyes = 0 THEN ''
    ELSE
      COALESCE(j.materials_by_kind, '')
      ||
      CASE
        WHEN j.n_dyes > 0 THEN
          CASE
            WHEN COALESCE(j.materials_by_kind, '') = '' THEN 'dye'
            ELSE '; dye'
          END
        ELSE ''
      END
  END AS treatment_display

FROM joined j;

COMMIT;

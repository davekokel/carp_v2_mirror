BEGIN;

-- Rebuild v11_treatment_label_star without using inj.fusion_pretty/organelle_fluors
-- as fallbacks for the style fields. We ONLY trust v11_treatment_star rollups for
-- fluor_tag_style and fluor_organelle_style. If those are empty, the style is empty.

CREATE OR REPLACE VIEW public.v11_treatment_label_star AS
WITH base AS (
  SELECT
    ts.treatment_id,
    ts.treatment_code AS treat_code,
    ts.kind_code,
    t.treatment_type,
    t.nickname,
    t.display_name,
    t.treat_text,
    t.notes,
    t.source_system,
    t.import_batch_id,
    t.created_at,
    ts.genotype_basecode_code,
    ts.materials_by_kind,
    ts.all_fluor_tag_rollup,
    ts.all_organelle_fluor_rollup
  FROM public.v11_treatment_star ts
  JOIN public.treatments t
    ON t.id::text = ts.treatment_id
),
mix_counts AS (
  SELECT
    tm.treatment_id::text AS treatment_id,
    count(*)::int AS n_mixes
  FROM public.treatment_mixes tm
  GROUP BY tm.treatment_id
),
construct_counts AS (
  SELECT
    tm.treatment_id::text AS treatment_id,
    count(DISTINCT tmc.construct_id)::int AS n_constructs
  FROM public.treatment_mixes tm
  JOIN public.treatment_mix_constructs tmc
    ON tmc.mix_id = tm.id
  GROUP BY tm.treatment_id
),
dye_counts AS (
  SELECT
    tm.treatment_id::text AS treatment_id,
    count(DISTINCT tmd.dye_id)::int AS n_dyes
  FROM public.treatment_mixes tm
  JOIN public.treatment_mix_dyes tmd
    ON tmd.mix_id = tm.id
  GROUP BY tm.treatment_id
),
ingredient_kinds AS (
  SELECT
    x.treatment_id::text AS treatment_id,
    string_agg(DISTINCT x.ingredient_kind, ', ' ORDER BY x.ingredient_kind) AS ingredient_kinds,
    count(DISTINCT x.ingredient_kind)::int AS n_kinds
  FROM (
    SELECT
      tm.treatment_id,
      COALESCE(c.construct_kind, 'plasmid') AS ingredient_kind
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
  GROUP BY x.treatment_id
),
inj_markers AS (
  -- We KEEP inj_markers only for treatment_display (plasmid(mgco-59)),
  -- NOT as fallback for fluor_tag_style / fluor_organelle_style.
  SELECT
    t.id::text AS treatment_id,
    lower(regexp_replace(t.treat_code, '^INJ-'::text, ''::text)) AS inj_base_code
  FROM public.treatments t
  WHERE t.treat_code ~~* 'INJ-%'
),
labelled AS (
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
    COALESCE(m.n_mixes, 0)           AS n_mixes,
    COALESCE(cc.n_constructs, 0)     AS n_constructs,
    COALESCE(dc.n_dyes, 0)           AS n_dyes,
    COALESCE(k.ingredient_kinds, '') AS ingredient_kinds,
    COALESCE(k.n_kinds, 0)           AS n_kinds,
    b.genotype_basecode_code,
    b.materials_by_kind,
    -- IMPORTANT: styles only come from v11_treatment_star rollups now.
    NULLIF(b.all_fluor_tag_rollup, '')      AS fluor_tag_style,
    NULLIF(b.all_organelle_fluor_rollup, '') AS fluor_organelle_style,
    CASE
      WHEN NULLIF(b.materials_by_kind, '') IS NOT NULL
        THEN b.materials_by_kind
      WHEN inj.inj_base_code IS NOT NULL
        THEN 'plasmid(' || inj.inj_base_code || ')'
      ELSE ''
    END AS treatment_display
  FROM base b
  LEFT JOIN mix_counts     m   ON m.treatment_id = b.treatment_id
  LEFT JOIN construct_counts cc ON cc.treatment_id = b.treatment_id
  LEFT JOIN dye_counts     dc  ON dc.treatment_id = b.treatment_id
  LEFT JOIN ingredient_kinds k ON k.treatment_id = b.treatment_id
  LEFT JOIN inj_markers    inj ON inj.treatment_id = b.treatment_id
)
SELECT
  treatment_id,
  treat_code,
  kind_code,
  treatment_type,
  nickname,
  display_name,
  treat_text,
  notes,
  source_system,
  import_batch_id,
  created_at,
  n_mixes,
  n_constructs,
  n_dyes,
  ingredient_kinds,
  n_kinds,
  genotype_basecode_code,
  materials_by_kind,
  fluor_tag_style,
  fluor_organelle_style,
  treatment_display
FROM labelled;

COMMIT;

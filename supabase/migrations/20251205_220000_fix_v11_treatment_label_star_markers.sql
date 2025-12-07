BEGIN;

-- Drop dependent fish view first, then treatment label view
DROP VIEW IF EXISTS public.v11_fish_instance_star_labels;
DROP VIEW IF EXISTS public.v11_treatment_label_star;

-- ── Recreate v11_treatment_label_star (known-good definition) ────────────────
CREATE VIEW public.v11_treatment_label_star AS
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
    COUNT(*)::integer     AS n_mixes
  FROM public.treatment_mixes tm
  GROUP BY tm.treatment_id
),
construct_counts AS (
  SELECT
    tm.treatment_id::text AS treatment_id,
    COUNT(DISTINCT tmc.construct_id)::integer AS n_constructs
  FROM public.treatment_mixes tm
  JOIN public.treatment_mix_constructs tmc
    ON tmc.mix_id = tm.id
  GROUP BY tm.treatment_id
),
dye_counts AS (
  SELECT
    tm.treatment_id::text AS treatment_id,
    COUNT(DISTINCT tmd.dye_id)::integer AS n_dyes
  FROM public.treatment_mixes tm
  JOIN public.treatment_mix_dyes tmd
    ON tmd.mix_id = tm.id
  GROUP BY tm.treatment_id
),
ingredient_kinds AS (
  SELECT
    x.treatment_id::text AS treatment_id,
    string_agg(DISTINCT x.ingredient_kind, ', ' ORDER BY x.ingredient_kind) AS ingredient_kinds,
    COUNT(DISTINCT x.ingredient_kind)::integer AS n_kinds
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
  ) AS x
  GROUP BY x.treatment_id
),
inj_markers AS (
  SELECT
    t.id::text AS treatment_id,
    lower(regexp_replace(t.treat_code, '^INJ-'::text, ''::text)) AS inj_base_code,
    v.fusion_pretty,
    v.organelle_fluors
  FROM public.treatments t
  LEFT JOIN public.constructs c
    ON lower(c.base_code) = lower(regexp_replace(t.treat_code, '^INJ-'::text, ''::text))
    OR lower(c.construct_code) = lower(regexp_replace(t.treat_code, '^INJ-'::text, ''::text))
  LEFT JOIN public.v_constructs_overview v
    ON v.construct_code = c.construct_code
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
    COALESCE(m.n_mixes, 0)                 AS n_mixes,
    COALESCE(cc.n_constructs, 0)           AS n_constructs,
    COALESCE(dc.n_dyes, 0)                 AS n_dyes,
    COALESCE(k.ingredient_kinds, ''::text) AS ingredient_kinds,
    COALESCE(k.n_kinds, 0)                 AS n_kinds,
    b.genotype_basecode_code,
    b.materials_by_kind,
    COALESCE(NULLIF(b.all_fluor_tag_rollup, ''::text), inj.fusion_pretty, ''::text)     AS fluor_tag_style,
    COALESCE(NULLIF(b.all_organelle_fluor_rollup, ''::text), inj.organelle_fluors, ''::text) AS fluor_organelle_style,
    CASE
      WHEN NULLIF(b.materials_by_kind, ''::text) IS NOT NULL THEN b.materials_by_kind
      WHEN inj.inj_base_code IS NOT NULL THEN 'plasmid(' || inj.inj_base_code || ')'
      ELSE ''::text
    END AS treatment_display
  FROM base b
  LEFT JOIN mix_counts       m   ON m.treatment_id = b.treatment_id
  LEFT JOIN construct_counts cc  ON cc.treatment_id = b.treatment_id
  LEFT JOIN dye_counts       dc  ON dc.treatment_id = b.treatment_id
  LEFT JOIN ingredient_kinds k   ON k.treatment_id = b.treatment_id
  LEFT JOIN inj_markers      inj ON inj.treatment_id = b.treatment_id
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

-- ── Recreate v11_fish_instance_star_labels depending on the new treatment_label view ──
CREATE VIEW public.v11_fish_instance_star_labels AS
WITH base AS (
  SELECT
    fis.fish_instance_id,
    fis.fish_code,
    fis.birthday,
    fis.instance_stage,
    fis.line_code,
    fis.line_nickname,
    fis.genetic_background,
    fis.line_construct_code,
    fis.allele_canonical_rollup,
    fis.allele_label_rollup,
    fis.genotype_basecodes,
    fis.genotype_v11_id,
    fis.genotype_code,
    fis.genotype_pretty,
    COALESCE(fls_lbl.genotype_tg_style,       fis.genotype_pretty) AS genotype_tg_style,
    COALESCE(fmrn.fluor_tag_rollup,           fis.genotype_pretty) AS genotype_fluortag_style,
    COALESCE(fmrn.organelle_fluor_rollup,     fis.genotype_pretty) AS genotype_fluororganelle_style
  FROM public.v11_fish_instance_star fis
  LEFT JOIN public.v11_fish_line_star_labels fls_lbl
    ON fls_lbl.line_code = fis.line_code
  LEFT JOIN public.v11_fish_marker_rollups_nice fmrn
    ON fmrn.fish_instance_id = fis.fish_instance_id
),
treat_rollups AS (
  SELECT
    jft.fish_instance_id AS fish_instance_id,
    string_agg(
      DISTINCT t.treat_code,
      ' || ' ORDER BY t.treat_code
    ) AS treatment_codes,
    string_agg(
      DISTINCT NULLIF(tls.treatment_display, ''),
      ' || ' ORDER BY NULLIF(tls.treatment_display, '')
    ) AS treatment_label_tg_style,
    string_agg(
      DISTINCT NULLIF(tls.fluor_tag_style, ''),
      ' || ' ORDER BY NULLIF(tls.fluor_tag_style, '')
    ) AS treatment_label_fluortag_style,
    string_agg(
      DISTINCT NULLIF(tls.fluor_organelle_style, ''),
      ' || ' ORDER BY NULLIF(tls.fluor_organelle_style, '')
    ) AS treatment_label_fluororganelle_style
  FROM public.join_fish_treatments jft
  JOIN public.treatments t
    ON t.id = jft.treatment_id
  LEFT JOIN public.v11_treatment_label_star tls
    ON tls.treat_code = t.treat_code
  GROUP BY jft.fish_instance_id
)
SELECT
  b.*,
  COALESCE(tr.treatment_codes, '')                      AS treatment_codes,
  COALESCE(tr.treatment_label_tg_style, '')             AS treatment_label_tg_style,
  COALESCE(tr.treatment_label_fluortag_style, '')       AS treatment_label_fluortag_style,
  COALESCE(tr.treatment_label_fluororganelle_style, '') AS treatment_label_fluororganelle_style
FROM base b
LEFT JOIN treat_rollups tr
  ON tr.fish_instance_id = b.fish_instance_id;

COMMIT;

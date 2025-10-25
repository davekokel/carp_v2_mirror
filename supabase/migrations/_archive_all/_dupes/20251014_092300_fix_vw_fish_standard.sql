CREATE OR REPLACE VIEW public.v_fish_standard AS
WITH base AS (
  SELECT
    f.id                             AS id,
    f.fish_code,
    COALESCE(f.name, ''::text)       AS name,
    COALESCE(f.nickname, ''::text)   AS nickname,
    f.date_birth,
    f.created_at,
    COALESCE(f.created_by, ''::text) AS created_by_raw
  FROM public.fish f
),
label AS (
  SELECT
    v.fish_code,
    v.genotype_print                                        AS genotype,
    COALESCE(v.genetic_background_print, v.genetic_background)         AS genetic_background,
    COALESCE(v.line_building_stage, v.line_building_stage_print)       AS stage,
    v.batch_label,
    v.seed_batch_id,
    v.transgene_base_code_filled                           AS transgene_base_code,
    v.allele_code_filled                                   AS allele_code,
    v.created_by_enriched,
    NULLIF(v.plasmid_injections_text, ''::text)            AS plasmid_injections_text,
    NULLIF(v.rna_injections_text, ''::text)                AS rna_injections_text
  FROM public.v_fish_overview_with_label v
),
tank_counts AS (
  SELECT
    m.fish_id,
    COUNT(*)::integer AS n_living_tanks
  FROM public.fish_tank_memberships m
  JOIN public.containers c ON c.id = m.container_id
  WHERE m.left_at IS NULL
    AND c.container_type = 'inventory_tank'::text
    AND c.deactivated_at IS NULL
    AND COALESCE(c.status, ''::text) = ANY (ARRAY['active'::text, 'planned'::text])
  GROUP BY m.fish_id
),
roll AS (
  SELECT
    l1.fish_code,
    TRIM(BOTH '; ' FROM concat_ws('; ',
      CASE WHEN l1.plasmid_injections_text IS NOT NULL THEN 'plasmid: '||l1.plasmid_injections_text END,
      CASE WHEN l1.rna_injections_text     IS NOT NULL THEN 'RNA: '     ||l1.rna_injections_text     END
    )) AS treatments_rollup
  FROM label l1
)
SELECT
  b.id,
  b.fish_code,
  b.name,
  b.nickname,
  l.genotype,
  l.genetic_background,
  l.stage,
  b.date_birth,
  (CURRENT_DATE - b.date_birth) AS age_days,
  b.created_at,
  COALESCE(l.created_by_enriched, b.created_by_raw) AS created_by,
  COALESCE(l.batch_label, l.seed_batch_id)          AS batch_display,
  l.transgene_base_code,
  l.allele_code,
  r.treatments_rollup,
  COALESCE(t.n_living_tanks, 0) AS n_living_tanks
FROM base b
LEFT JOIN label l USING (fish_code)
LEFT JOIN roll  r USING (fish_code)
LEFT JOIN tank_counts t ON t.fish_id = b.id;

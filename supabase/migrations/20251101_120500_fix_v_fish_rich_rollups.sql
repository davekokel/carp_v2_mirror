BEGIN;

DROP VIEW IF EXISTS public.v_fish_rich;

-- v_fish_rich with allele aggregates + genetic fusion/fluor/tag rollups
-- Assumes:
--  join_fish_transgene_alleles(j.fish_id, transgene_base_code, allele_number)
--  transgene_alleles(transgene_base_code, allele_number, allele_name)
--  join_plasmid_fusions(plasmid_code, fusion_code)
--  fusions(fusion_code, fusion_name, fluor_code, tag_code)
--  fluors(fluor_code, fluor_name), tags(tag_code, tag_name)
--  join_fish_tanks(j.fish_id, j.tank_id/uuid/code) — used only for DISTINCT count

CREATE VIEW public.v_fish_rich AS
WITH
links AS (
  SELECT
    j.fish_id                 AS fish_uuid,
    j.transgene_base_code     AS base_code,
    j.allele_number           AS allele_number
  FROM public.join_fish_transgene_alleles j
),
alleles AS (
  SELECT
    l.fish_uuid,
    l.base_code,
    l.allele_number,
    ta.allele_name
  FROM links l
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = l.base_code
   AND ta.allele_number       = l.allele_number
),
ai AS (  -- pretty strings for allele aggregates
  SELECT
    a.fish_uuid,
    a.base_code,
    (a.base_code || '/' || a.allele_name)           AS acode,
    ('Tg(' || a.base_code || ')' || a.allele_name)  AS apretty
  FROM alleles a
),
agg AS (
  SELECT
    ai.fish_uuid,
    COUNT(*)::int                                                   AS allele_number,
    string_agg(DISTINCT ai.acode,     ', ' ORDER BY ai.acode)       AS allele_code,
    string_agg(DISTINCT ai.base_code, ', ' ORDER BY ai.base_code)   AS transgene,
    string_agg(ai.apretty,           '; '  ORDER BY ai.apretty)     AS genotype_rollup
  FROM ai
  GROUP BY ai.fish_uuid
),
gx AS (  -- genetic fusions/tags/fluors via plasmid wiring
  SELECT
    j.fish_id         AS fish_uuid,
    fu.fusion_name,
    fl.fluor_name,
    tg.tag_name
  FROM public.join_fish_transgene_alleles j
  JOIN public.join_plasmid_fusions pf ON pf.plasmid_code = j.transgene_base_code
  JOIN public.fusions            fu   ON fu.fusion_code  = pf.fusion_code
  LEFT JOIN public.fluors        fl   ON fl.fluor_code   = fu.fluor_code
  LEFT JOIN public.tags          tg   ON tg.tag_code     = fu.tag_code
),
groll AS (
  SELECT
    fish_uuid,
    string_agg(DISTINCT fusion_name, ', ' ORDER BY fusion_name)                         AS fusion_rollup,
    string_agg(DISTINCT fluor_name,  ', ' ORDER BY fluor_name)  FILTER (WHERE fluor_name IS NOT NULL) AS fluor_rollup_genetic,
    string_agg(DISTINCT tag_name,    ', ' ORDER BY tag_name)    FILTER (WHERE tag_name   IS NOT NULL) AS tag_rollup_genetic
  FROM gx
  GROUP BY fish_uuid
),
tanks AS (  -- distinct tank links per fish (any status)
  SELECT j.fish_id AS fish_uuid, COUNT(DISTINCT j.tank_id)::int AS n_active_tanks
  FROM public.join_fish_tanks j
  GROUP BY j.fish_id
)
SELECT
  f.id                          AS fish_uuid,
  f.fish_code                   AS fish_code,
  f.name_human                  AS fish_name,
  f.nickname                    AS fish_nickname,
  f.genetic_background          AS genetic_background,
  f.line_building_stage         AS line_building_stage,
  f.description                 AS description,
  f.dob                         AS dob,
  COALESCE(a.allele_number, 0)  AS allele_number,
  COALESCE(a.allele_code,   '') AS allele_code,
  COALESCE(a.transgene,     '') AS transgene,
  COALESCE(a.genotype_rollup,'')AS genotype_rollup,
  COALESCE(t.n_active_tanks, 0) AS n_active_tanks,
  f.created_at                  AS created_at,
  COALESCE(gr.fusion_rollup,        '') AS fusion_rollup,
  COALESCE(gr.fluor_rollup_genetic, '') AS fluor_rollup_genetic,
  COALESCE(gr.tag_rollup_genetic,   '') AS tag_rollup_genetic,
  -- Placeholder combined rollup; later union in treatment-derived fluors
  COALESCE(gr.fluor_rollup_genetic, '') AS fluor_rollup
FROM public.fish f
LEFT JOIN agg    a  ON a.fish_uuid  = f.id
LEFT JOIN groll  gr ON gr.fish_uuid = f.id
LEFT JOIN tanks  t  ON t.fish_uuid  = f.id
ORDER BY f.fish_code;

COMMIT;

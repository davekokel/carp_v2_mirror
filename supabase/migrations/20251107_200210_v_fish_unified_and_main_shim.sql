BEGIN;

-- Recreate v_fish_unified with a safe DISTINCT + ORDER BY pattern and
-- without referencing v_fish_main (avoid recursion).
DROP VIEW IF EXISTS public.v_fish_unified;

CREATE VIEW public.v_fish_unified AS
WITH markers AS (
  SELECT
    f.fish_code,
    (ta.transgene_base_code || '(' || ta.allele_name || ')')::text AS marker_label
  FROM public.join_fish_transgene_alleles jf
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = jf.transgene_base_code
   AND ta.allele_number       = jf.allele_number
  JOIN public.fish f
    ON f.id = jf.fish_id
  WHERE NULLIF(ta.allele_name,'') IS NOT NULL
),
gp AS (
  SELECT
    m.fish_code,
    string_agg(DISTINCT m.marker_label, ', ' ORDER BY m.marker_label) AS genotype_pretty
  FROM markers m
  GROUP BY m.fish_code
),
mr AS (
  SELECT r.fish_code, r.markers, r.fluors, r.tags, r.dyes
  FROM public.v_fluorescent_marker_rollup r
)
SELECT
  f.fish_code,
  f.nickname,
  f.birthday,
  f.genetic_background,
  f.line_building_stage,
  COALESCE(gp.genotype_pretty,'') AS genotype_pretty,
  COALESCE(mr.markers,'')         AS markers,
  COALESCE(mr.fluors,'')          AS fluors,
  COALESCE(mr.tags,'')            AS tags,
  COALESCE(mr.dyes,'')            AS dyes,
  f.created_at
FROM public.fish f
LEFT JOIN gp ON gp.fish_code = f.fish_code
LEFT JOIN mr ON mr.fish_code = f.fish_code;

-- OPTIONAL: Make v_fish_main a shim over unified now that unified is independent.
-- If you have a bespoke v_fish_main you want to keep, comment this block out.
DROP VIEW IF EXISTS public.v_fish_main;
CREATE VIEW public.v_fish_main AS
SELECT * FROM public.v_fish_unified;

COMMIT;

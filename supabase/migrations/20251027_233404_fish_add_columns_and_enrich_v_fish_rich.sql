BEGIN;

-- 1) Ensure the base columns exist on public.fish
ALTER TABLE public.fish
  ADD COLUMN IF NOT EXISTS fish_name           text,
  ADD COLUMN IF NOT EXISTS fish_nickname       text,
  ADD COLUMN IF NOT EXISTS genetic_background  text,
  ADD COLUMN IF NOT EXISTS line_building_stage text,
  ADD COLUMN IF NOT EXISTS date_birth          date;

-- 2) Rebuild v_fish_rich with real + derived fields (no dependency on external views for counts)
--    Joins to genotype/allele views are safe even if shims are in place.
CREATE OR REPLACE VIEW public.v_fish_rich AS
SELECT
  f.fish_uuid::uuid                  AS fish_uuid,
  f.fish_code::text                  AS fish_code,
  COALESCE(f.fish_name,'')::text     AS fish_name,
  COALESCE(f.fish_nickname,'')::text AS fish_nickname,
  COALESCE(f.genetic_background,'')::text AS genetic_background,
  COALESCE(f.line_building_stage,'')::text AS line_building_stage,
  f.date_birth::date                 AS date_birth,
  -- derived: allele summary (from v_transgene_alleles, shim or real)
  COALESCE(a.allele_number,0)::int   AS allele_number,
  COALESCE(a.allele_code,'')::text   AS allele_code,
  -- derived: active tank count (correlated subquery, no external view dependency)
  COALESCE((
    SELECT COUNT(*) FROM public.fish_tank_memberships m
    JOIN public.tanks t ON t.tank_uuid = m.tank_uuid
    WHERE m.fish_uuid = f.fish_uuid AND t.status = 'active'
  ),0)::int                          AS n_active_tanks,
  -- pretty / rollup (from v_fish_genotypes, shim or real)
  COALESCE(g.transgene_pretty,'')::text  AS transgene_pretty,
  COALESCE(g.genotype_rollup,'')::text   AS genotype_rollup,
  f.created_at::timestamptz          AS created_at
FROM public.fish f
LEFT JOIN public.v_transgene_alleles a ON a.fish_uuid = f.fish_uuid
LEFT JOIN public.v_fish_genotypes   g ON g.fish_uuid = f.fish_uuid;

COMMIT;

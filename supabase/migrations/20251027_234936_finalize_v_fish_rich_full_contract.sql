CREATE OR REPLACE VIEW public.v_fish_rich AS
WITH tcounts AS (
  SELECT m.fish_uuid, COUNT(*)::int AS n_active_tanks
  FROM public.fish_tank_memberships m
  JOIN public.tanks t ON t.tank_uuid = m.tank_uuid
  WHERE t.status = 'active'
  GROUP BY m.fish_uuid
)
SELECT
  f.fish_uuid::uuid                     AS fish_uuid,
  f.fish_code::text                     AS fish_code,
  COALESCE(f.fish_name,'')::text        AS fish_name,
  COALESCE(f.fish_nickname,'')::text    AS fish_nickname,
  COALESCE(f.genetic_background,'')::text    AS genetic_background,
  COALESCE(f.line_building_stage,'')::text   AS line_building_stage,
  f.date_birth::date                    AS date_birth,
  COALESCE(a.allele_number,0)::int      AS allele_number,
  COALESCE(a.allele_code,'')::text      AS allele_code,
  COALESCE(tc.n_active_tanks,0)::int    AS n_active_tanks,
  COALESCE(g.transgene_pretty,'')::text AS transgene_pretty,
  COALESCE(g.genotype_rollup,'')::text  AS genotype_rollup,
  f.created_at::timestamptz             AS created_at
FROM public.fish f
LEFT JOIN tcounts tc                 ON tc.fish_uuid   = f.fish_uuid
LEFT JOIN public.v_transgene_alleles a ON a.fish_uuid   = f.fish_uuid   -- shim or real
LEFT JOIN public.v_fish_genotypes   g ON g.fish_uuid   = f.fish_uuid;   -- shim or real

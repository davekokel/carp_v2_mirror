-- Safe rebuild of v_fish_rich with full contract
-- Drops stub version first to allow column additions/renames
DROP VIEW IF EXISTS public.v_fish_rich CASCADE;

CREATE VIEW public.v_fish_rich AS
WITH tcounts AS (
  SELECT m.fish_uuid, COUNT(*)::int AS n_active_tanks
  FROM public.fish_tank_memberships m
  JOIN public.tanks t ON t.tank_uuid = m.tank_uuid
  WHERE t.status = 'active'
  GROUP BY m.fish_uuid
)
SELECT
  f.fish_uuid::uuid                      AS fish_uuid,
  f.fish_code::text                      AS fish_code,
  COALESCE(f.fish_name, '')::text        AS fish_name,
  COALESCE(f.fish_nickname, '')::text    AS fish_nickname,
  COALESCE(f.genetic_background, '')::text AS genetic_background,
  COALESCE(f.line_building_stage, '')::text AS line_building_stage,
  f.date_birth::date                     AS date_birth,
  0::int                                 AS allele_number,
  NULL::text                             AS allele_code,
  COALESCE(tc.n_active_tanks, 0)::int    AS n_active_tanks,
  NULL::text                             AS transgene_pretty,
  NULL::text                             AS genotype_rollup,
  f.created_at::timestamptz              AS created_at
FROM public.fish f
LEFT JOIN tcounts tc ON tc.fish_uuid = f.fish_uuid;

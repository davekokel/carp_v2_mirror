-- Backfill modern columns once from legacy if modern is empty
UPDATE public.fish
SET fish_name = name
WHERE (fish_name IS NULL OR fish_name = '')
  AND name IS NOT NULL AND name <> '';

UPDATE public.fish
SET fish_nickname = nickname
WHERE (fish_nickname IS NULL OR fish_nickname = '')
  AND nickname IS NOT NULL AND nickname <> '';

-- Make v_fish_rich tolerant: prefer fish_name/fish_nickname, fall back to legacy
CREATE OR REPLACE VIEW public.v_fish_rich AS
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
  COALESCE(f.fish_name, f.name, '')::text         AS fish_name,
  COALESCE(f.fish_nickname, f.nickname, '')::text AS fish_nickname,
  f.genetic_background::text             AS genetic_background,
  f.line_building_stage::text            AS line_building_stage,
  f.date_birth::date                     AS date_birth,
  0::int                                 AS allele_number,
  NULL::text                             AS allele_code,
  COALESCE(tc.n_active_tanks,0)::int     AS n_active_tanks,
  NULL::text                             AS transgene_pretty,
  NULL::text                             AS genotype_rollup,
  f.created_at::timestamptz              AS created_at
FROM public.fish f
LEFT JOIN tcounts tc ON tc.fish_uuid = f.fish_uuid;

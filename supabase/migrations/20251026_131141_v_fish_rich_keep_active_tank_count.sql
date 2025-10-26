CREATE OR REPLACE VIEW public.v_fish_rich_keep_active_tank_count AS
WITH
base AS (
  SELECT
    f.fish_uuid,
    f.fish_code,
    f.name                AS fish_name,
    f.nickname            AS fish_nickname,
    f.genetic_background,
    f.line_building_stage,
    f.created_at          AS fish_created_at,
    f.created_by          AS fish_created_by,
    f.date_birth
  FROM public.fish f
),
live_cte AS (
  SELECT
    m.fish_uuid,
    COUNT(*) FILTER (WHERE m.ended_at IS NULL)::int AS n_living_tanks_derived
  FROM public.fish_tank_memberships m
  GROUP BY m.fish_uuid
),
active_tanks AS (
  SELECT
    m.fish_uuid,
    COUNT(*) FILTER (
      WHERE m.ended_at IS NULL
        AND COALESCE(t.status,'active') IN ('active','living')
    )::int AS active_tank_count
  FROM public.fish_tank_memberships m
  JOIN public.tanks t ON t.tank_uuid = m.tank_uuid
  GROUP BY m.fish_uuid
)
SELECT
  b.fish_uuid,
  b.fish_code,
  b.fish_name,
  b.fish_nickname,
  b.genetic_background,
  b.line_building_stage,
  COALESCE(l.n_living_tanks_derived, 0) AS n_living_tanks,
  COALESCE(a.active_tank_count, 0)      AS active_tank_count,
  b.fish_created_at,
  b.fish_created_by,
  b.date_birth
FROM base b
LEFT JOIN live_cte     l USING (fish_uuid)
LEFT JOIN active_tanks a USING (fish_uuid);

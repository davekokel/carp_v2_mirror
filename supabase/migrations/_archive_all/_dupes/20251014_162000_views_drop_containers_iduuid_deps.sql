CREATE OR REPLACE VIEW public.v_containers_candidates AS
SELECT
  c.id              AS id_uuid,
  c.container_type,
  c.label,
  c.status,
  c.created_by,
  c.created_at,
  c.status_changed_at,
  c.activated_at,
  c.deactivated_at,
  c.last_seen_at,
  c.note
FROM public.containers c
WHERE c.container_type IN ('inventory_tank','crossing_tank','holding_tank','nursery_tank','petri_dish');

CREATE OR REPLACE VIEW public.v_containers AS
SELECT
  c.id              AS id_uuid,
  c.container_type,
  c.label,
  c.status,
  c.created_by,
  c.created_at,
  c.note,
  c.request_id,
  c.status_changed_at,
  c.activated_at,
  c.deactivated_at,
  c.last_seen_at,
  c.last_seen_source,
  c.tank_volume_l,
  c.tank_code
FROM public.containers c
WHERE c.status IN ('active','new_tank');

CREATE OR REPLACE VIEW public.v_cross_plan_runs_enriched AS
SELECT
  r.id                       AS id,
  r.plan_id,
  r.seq,
  r.planned_date,
  r.status,
  r.note,
  r.created_by,
  r.created_at,
  p.plan_title,
  p.plan_nickname,
  p.mother_fish_id,
  p.father_fish_id,
  fm.fish_code               AS mother_fish_code,
  ff.fish_code               AS father_fish_code,
  ca.label                   AS tank_a_label,
  cb.label                   AS tank_b_label
FROM public.cross_plan_runs r
LEFT JOIN public.cross_plans p ON p.id = r.plan_id
LEFT JOIN public.fish fm       ON fm.id = p.mother_fish_id
LEFT JOIN public.fish ff       ON ff.id = p.father_fish_id
LEFT JOIN public.containers ca ON ca.id = r.tank_a_id
LEFT JOIN public.containers cb ON cb.id = r.tank_b_id;

CREATE OR REPLACE VIEW public.v_cross_plans_enriched AS
SELECT
  p.id                       AS id,
  p.plan_date,
  p.status,
  p.created_by,
  p.note,
  p.created_at,
  p.mother_fish_id,
  fm.fish_code               AS mother_fish_code,
  p.father_fish_id,
  ff.fish_code               AS father_fish_code,
  p.tank_a_id,
  ca.label                   AS tank_a_label,
  p.tank_b_id,
  cb.label                   AS tank_b_label
FROM public.cross_plans p
LEFT JOIN public.fish fm       ON fm.id = p.mother_fish_id
LEFT JOIN public.fish ff       ON ff.id = p.father_fish_id
LEFT JOIN public.containers ca ON ca.id = p.tank_a_id
LEFT JOIN public.containers cb ON cb.id = p.tank_b_id;

CREATE OR REPLACE VIEW public.v_fish_living_tank_counts AS
SELECT
  m.fish_id,
  COUNT(*)::int AS n_living_tanks
FROM public.fish_tank_memberships m
JOIN public.containers c ON c.id = m.container_id
WHERE m.left_at IS NULL
  AND c.status IN ('active','new_tank')
GROUP BY m.fish_id;

CREATE OR REPLACE VIEW public.v_fish_standard AS
WITH base AS (
  SELECT
    f.id                       AS id_uuid,
    f.fish_code,
    COALESCE(f.name,'')        AS name,
    COALESCE(f.nickname,'')    AS nickname,
    f.date_birth,
    f.created_at,
    COALESCE(f.created_by,'')  AS created_by_raw
  FROM public.fish f
), tank_counts AS (
  SELECT m.fish_id, count(*)::int AS n_living_tanks
  FROM public.fish_tank_memberships m
  JOIN public.containers c ON c.id = m.container_id
  WHERE m.left_at IS NULL
    AND c.container_type='inventory_tank'
    AND c.deactivated_at IS NULL
    AND COALESCE(c.status,'') IN ('active','planned')
  GROUP BY m.fish_id
)
SELECT
  b.id_uuid,
  b.fish_code,
  b.name,
  b.nickname,
  NULL::text                 AS genotype,
  NULL::text                 AS genetic_background,
  NULL::text                 AS stage,
  b.date_birth,
  (CURRENT_DATE - b.date_birth) AS age_days,
  b.created_at,
  b.created_by_raw           AS created_by,
  NULL::text                 AS batch_display,
  NULL::text                 AS transgene_base_code,
  NULL::text                 AS allele_code,
  NULL::text                 AS treatments_rollup,
  COALESCE(t.n_living_tanks,0) AS n_living_tanks
FROM base b
LEFT JOIN tank_counts t ON t.fish_id = b.id_uuid;

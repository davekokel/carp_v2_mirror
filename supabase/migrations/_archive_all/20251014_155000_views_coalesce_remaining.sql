-- v_cross_plan_runs_enriched
CREATE OR REPLACE VIEW public.v_cross_plan_runs_enriched AS
SELECT
  r.id                       AS id,               -- plan run id stays as-is if this table already has id
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
LEFT JOIN public.containers ca ON COALESCE(ca.id, ca.id_uuid) = r.tank_a_id
LEFT JOIN public.containers cb ON COALESCE(cb.id, cb.id_uuid) = r.tank_b_id;

-- v_cross_plans_enriched
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
LEFT JOIN public.containers ca ON COALESCE(ca.id, ca.id_uuid) = p.tank_a_id
LEFT JOIN public.containers cb ON COALESCE(cb.id, cb.id_uuid) = p.tank_b_id;

-- v_fish_living_tank_counts
CREATE OR REPLACE VIEW public.v_fish_living_tank_counts AS
SELECT
  m.fish_id,
  COUNT(*)::int AS n_living_tanks
FROM public.fish_tank_memberships m
JOIN public.containers c ON COALESCE(c.id, c.id_uuid) = m.container_id
WHERE m.left_at IS NULL
  AND c.status IN ('active','new_tank')
GROUP BY m.fish_id;

-- vw_cross_runs_overview
CREATE OR REPLACE VIEW public.vw_cross_runs_overview AS
WITH cl AS (
  SELECT clutches.cross_instance_id, COUNT(*)::int AS n_clutches
  FROM public.clutches
  GROUP BY clutches.cross_instance_id
), cnt AS (
  SELECT c.cross_instance_id, COUNT(cc.*)::int AS n_containers
  FROM public.clutches c
  JOIN public.clutch_containers cc ON cc.clutch_id = c.id_uuid
  GROUP BY c.cross_instance_id
)
SELECT
  ci.id                AS cross_instance_id,
  ci.cross_run_code,
  ci.cross_date,
  x.id                 AS cross_id,
  COALESCE(x.cross_code, x.id::text) AS cross_code,
  x.mother_code        AS mom_code,
  x.father_code        AS dad_code,
  cm.label             AS mother_tank_label,
  cf.label             AS father_tank_label,
  ci.note              AS run_note,
  ci.created_by        AS run_created_by,
  ci.created_at        AS run_created_at,
  COALESCE(cl.n_clutches,0) AS n_clutches,
  COALESCE(cnt.n_containers,0) AS n_containers
FROM public.cross_instances ci
JOIN public.crosses x          ON x.id = ci.cross_id
LEFT JOIN public.containers cm ON COALESCE(cm.id, cm.id_uuid) = ci.mother_tank_id
LEFT JOIN public.containers cf ON COALESCE(cf.id, cf.id_uuid) = ci.father_tank_id
LEFT JOIN cl ON cl.cross_instance_id = ci.id
LEFT JOIN cnt ON cnt.cross_instance_id = ci.id
ORDER BY ci.cross_date DESC, ci.created_at DESC;

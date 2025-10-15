-- Rewrites that eliminate table column dependencies on id_uuid (use only .id, alias as id_uuid)

-- v_containers_crossing_candidates
CREATE OR REPLACE VIEW public.v_containers_crossing_candidates AS
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

-- v_containers_live
CREATE OR REPLACE VIEW public.v_containers_live AS
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

-- v_cross_plan_runs_enriched
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
LEFT JOIN public.containers ca ON ca.id = p.tank_a_id
LEFT JOIN public.containers cb ON cb.id = p.tank_b_id;

-- v_fish_living_tank_counts
CREATE OR REPLACE VIEW public.v_fish_living_tank_counts AS
SELECT
  m.fish_id,
  COUNT(*)::int AS n_living_tanks
FROM public.fish_tank_memberships m
JOIN public.containers c ON c.id = m.container_id
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
  COALESCE(cl.n_clutches,0)   AS n_clutches,
  COALESCE(cnt.n_containers,0) AS n_containers
FROM public.cross_instances ci
JOIN public.crosses x          ON x.id = ci.cross_id
LEFT JOIN public.containers cm ON cm.id = ci.mother_tank_id
LEFT JOIN public.containers cf ON cf.id = ci.father_tank_id
LEFT JOIN cl ON cl.cross_instance_id = ci.id
LEFT JOIN cnt ON cnt.cross_instance_id = ci.id
ORDER BY ci.cross_date DESC, ci.created_at DESC;

-- vw_clutches_overview_human
CREATE OR REPLACE VIEW public.vw_clutches_overview_human AS
WITH base AS (
  SELECT
    c.id_uuid               AS clutch_id,
    c.date_birth,
    c.created_by,
    c.created_at,
    c.note,
    c.batch_label,
    c.seed_batch_id,
    c.planned_cross_id,
    cp.clutch_code,
    cp.planned_name         AS clutch_name,
    COALESCE(mt.label, mt.tank_code) AS mom_tank_label,
    COALESCE(ft.label, ft.tank_code) AS dad_tank_label,
    c.cross_id
  FROM public.clutches c
  LEFT JOIN public.planned_crosses pc ON pc.id = c.planned_cross_id
  LEFT JOIN public.clutch_plans cp    ON cp.id = pc.clutch_id
  LEFT JOIN public.containers mt      ON mt.id = pc.mother_tank_id
  LEFT JOIN public.containers ft      ON ft.id = pc.father_tank_id
), instances AS (
  SELECT cc.clutch_id, count(*)::int AS n_instances
  FROM public.clutch_containers cc
  GROUP BY cc.clutch_id
), crosses_via_clutches AS (
  SELECT b.clutch_id, count(x.id_uuid)::int AS n_crosses
  FROM base b
  LEFT JOIN public.crosses x ON x.id_uuid = b.cross_id
  GROUP BY b.clutch_id
)
SELECT b.clutch_id, b.date_birth, b.created_by, b.created_at, b.note, b.batch_label, b.seed_batch_id,
       b.clutch_code, b.clutch_name,
       NULL::text AS clutch_nickname,
       b.mom_tank_label, b.dad_tank_label,
       COALESCE(i.n_instances,0) AS n_instances,
       COALESCE(cx.n_crosses,0)  AS n_crosses
FROM base b
LEFT JOIN instances i ON i.clutch_id = b.clutch_id
LEFT JOIN crosses_via_clutches cx ON cx.clutch_id = b.clutch_id
ORDER BY COALESCE(b.date_birth::timestamp, b.created_at) DESC NULLS LAST;

-- vw_fish_standard (keep alias id_uuid for compatibility)
CREATE OR REPLACE VIEW public.vw_fish_standard AS
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
  WHERE m.left_at IS NULL AND c.container_type='inventory_tank' AND c.deactivated_at IS NULL AND COALESCE(c.status,'') IN ('active','planned')
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

-- vw_label_rows (compact, id-only compatible)
CREATE OR REPLACE VIEW public.vw_label_rows AS
SELECT
  f.id AS id_uuid,
  f.created_at,
  f.fish_code,
  f.name,
  NULL::text AS transgene_base_code_filled,
  NULL::text AS allele_code_filled,
  NULL::text AS allele_name_filled,
  NULL::text AS batch_label,
  COALESCE(f.nickname,'') AS nickname_print,
  COALESCE(f.genetic_background,'') AS genetic_background_print,
  COALESCE(f.line_building_stage,'') AS line_building_stage_print,
  COALESCE(to_char((f.date_birth)::timestamp with time zone, 'YYYY-MM-DD'),'') AS date_birth_print,
  ''::text AS genotype_print
FROM public.fish f
ORDER BY f.fish_code;

-- vw_plasmids_overview
CREATE OR REPLACE VIEW public.vw_plasmids_overview AS
SELECT
  p.id          AS id_uuid,
  p.code,
  p.name,
  p.nickname,
  p.fluors,
  p.resistance,
  p.supports_invitro_rna,
  p.created_by,
  p.notes,
  p.created_at,
  r.id          AS rna_id,
  r.code        AS rna_code,
  r.name        AS rna_name,
  r.source_plasmid_id
FROM public.plasmids p
LEFT JOIN public.rnas r ON r.source_plasmid_id = p.id
ORDER BY p.code;

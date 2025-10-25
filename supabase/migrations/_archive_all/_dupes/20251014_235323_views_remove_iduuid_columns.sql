CREATE OR REPLACE VIEW public.v_containers_candidates AS
SELECT
  c.id              AS id,
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
  c.id              AS id,
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

CREATE OR REPLACE VIEW public.v_crosses_status AS
SELECT
  c.id,
  c.mother_code,
  c.father_code,
  c.planned_for,
  c.created_by,
  c.created_at,
  CASE WHEN EXISTS (SELECT 1 FROM public.clutches x WHERE x.cross_id = c.id)
       THEN 'realized' ELSE 'planned' END AS status
FROM public.crosses c;

CREATE OR REPLACE VIEW public.v_labels_recent AS
SELECT
  j.id AS id,
  j.entity_type,
  j.entity_id,
  j.template,
  j.media,
  j.status,
  j.requested_by,
  j.requested_at,
  j.started_at,
  j.finished_at,
  j.num_labels,
  ((j.file_bytes IS NOT NULL) OR (j.file_url IS NOT NULL)) AS has_file
FROM public.label_jobs j
ORDER BY j.requested_at DESC;

CREATE OR REPLACE VIEW public.v_fish_standard AS
WITH base AS (
  SELECT
    f.id                       AS id,
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
  b.id,
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
LEFT JOIN tank_counts t ON t.fish_id = b.id;

CREATE OR REPLACE VIEW public.v_label_rows AS
SELECT
  f.id AS id,
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

CREATE OR REPLACE VIEW public.v_plasmids AS
SELECT
  p.id          AS id,
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

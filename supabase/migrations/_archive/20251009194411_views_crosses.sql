BEGIN;
CREATE OR REPLACE VIEW public.vw_crosses_concept AS
WITH runs AS (
  SELECT cross_id, COUNT(*)::int n_runs, MAX(cross_date) latest_cross_date
  FROM public.cross_instances GROUP BY cross_id
), cl AS (
  SELECT cross_id, COUNT(*)::int n_clutches FROM public.clutches GROUP BY cross_id
), cnt AS (
  SELECT c.cross_id, COUNT(cc.*)::int n_containers
  FROM public.clutches c JOIN public.clutch_containers cc ON cc.clutch_id = c.id_uuid
  GROUP BY c.cross_id
)
SELECT x.id_uuid AS cross_id, COALESCE(x.cross_code, x.id_uuid::text) AS cross_code,
       x.mother_code AS mom_code, x.father_code AS dad_code,
       x.created_by, x.created_at,
       COALESCE(runs.n_runs,0) n_runs, runs.latest_cross_date,
       COALESCE(cl.n_clutches,0) n_clutches, COALESCE(cnt.n_containers,0) n_containers
FROM public.crosses x
LEFT JOIN runs ON runs.cross_id = x.id_uuid
LEFT JOIN cl   ON cl.cross_id   = x.id_uuid
LEFT JOIN cnt  ON cnt.cross_id  = x.id_uuid
ORDER BY x.created_at DESC;

CREATE OR REPLACE VIEW public.vw_cross_runs_overview AS
WITH cl AS (SELECT cross_instance_id, COUNT(*)::int n_clutches FROM public.clutches GROUP BY cross_instance_id),
cnt AS (
  SELECT c.cross_instance_id, COUNT(cc.*)::int n_containers
  FROM public.clutches c JOIN public.clutch_containers cc ON cc.clutch_id = c.id_uuid
  GROUP BY c.cross_instance_id
)
SELECT ci.id_uuid AS cross_instance_id, ci.cross_run_code, ci.cross_date,
       x.id_uuid AS cross_id, COALESCE(x.cross_code, x.id_uuid::text) AS cross_code,
       x.mother_code AS mom_code, x.father_code AS dad_code,
       cm.label AS mother_tank_label, cf.label AS father_tank_label,
       ci.note AS run_note, ci.created_by AS run_created_by, ci.created_at AS run_created_at,
       COALESCE(cl.n_clutches,0) n_clutches, COALESCE(cnt.n_containers,0) n_containers
FROM public.cross_instances ci
JOIN public.crosses x ON x.id_uuid = ci.cross_id
LEFT JOIN public.containers cm ON cm.id_uuid = ci.mother_tank_id
LEFT JOIN public.containers cf ON cf.id_uuid = ci.father_tank_id
LEFT JOIN cl  ON cl.cross_instance_id  = ci.id_uuid
LEFT JOIN cnt ON cnt.cross_instance_id = ci.id_uuid
ORDER BY ci.cross_date DESC, ci.created_at DESC;
COMMIT;

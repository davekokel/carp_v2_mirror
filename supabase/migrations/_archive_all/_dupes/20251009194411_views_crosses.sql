BEGIN;
CREATE OR REPLACE VIEW public.v_crosses_concept AS
WITH runs AS (
    SELECT
        cross_id,
        COUNT(*)::int AS n_runs,
        MAX(cross_date) AS latest_cross_date
    FROM public.cross_instances
    GROUP BY cross_id
),

cl AS (
    SELECT
        cross_id,
        COUNT(*)::int AS n_clutches
    FROM public.clutches
    GROUP BY cross_id
),

cnt AS (
    SELECT
        c.cross_id,
        COUNT(cc.*)::int AS n_containers
    FROM public.clutches AS c INNER JOIN public.clutch_containers AS cc ON c.id_uuid = cc.clutch_id
    GROUP BY c.cross_id
)

SELECT
    x.id_uuid AS cross_id,
    x.mother_code AS mom_code,
    x.father_code AS dad_code,
    x.created_by,
    x.created_at,
    runs.latest_cross_date,
    COALESCE(x.cross_code, x.id_uuid::text) AS cross_code,
    COALESCE(runs.n_runs, 0) AS n_runs,
    COALESCE(cl.n_clutches, 0) AS n_clutches,
    COALESCE(cnt.n_containers, 0) AS n_containers
FROM public.crosses AS x
LEFT JOIN runs ON x.id_uuid = runs.cross_id
LEFT JOIN cl ON x.id_uuid = cl.cross_id
LEFT JOIN cnt ON x.id_uuid = cnt.cross_id
ORDER BY x.created_at DESC;

CREATE OR REPLACE VIEW public.v_cross_runs AS
WITH cl AS (SELECT
    cross_instance_id,
    COUNT(*)::int AS n_clutches
FROM public.clutches
GROUP BY cross_instance_id),

cnt AS (
    SELECT
        c.cross_instance_id,
        COUNT(cc.*)::int AS n_containers
    FROM public.clutches AS c INNER JOIN public.clutch_containers AS cc ON c.id_uuid = cc.clutch_id
    GROUP BY c.cross_instance_id
)

SELECT
    ci.id_uuid AS cross_instance_id,
    ci.cross_run_code,
    ci.cross_date,
    x.id_uuid AS cross_id,
    x.mother_code AS mom_code,
    x.father_code AS dad_code,
    cm.label AS mother_tank_label,
    cf.label AS father_tank_label,
    ci.note AS run_note,
    ci.created_by AS run_created_by,
    ci.created_at AS run_created_at,
    COALESCE(x.cross_code, x.id_uuid::text) AS cross_code,
    COALESCE(cl.n_clutches, 0) AS n_clutches,
    COALESCE(cnt.n_containers, 0) AS n_containers
FROM public.cross_instances AS ci
INNER JOIN public.crosses AS x ON ci.cross_id = x.id_uuid
LEFT JOIN public.containers AS cm ON ci.mother_tank_id = cm.id_uuid
LEFT JOIN public.containers AS cf ON ci.father_tank_id = cf.id_uuid
LEFT JOIN cl ON ci.id_uuid = cl.cross_instance_id
LEFT JOIN cnt ON ci.id_uuid = cnt.cross_instance_id
ORDER BY ci.cross_date DESC, ci.created_at DESC;
COMMIT;

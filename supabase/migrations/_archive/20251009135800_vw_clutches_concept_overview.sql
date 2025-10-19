BEGIN;

CREATE OR REPLACE VIEW public.vw_clutches_concept_overview AS
WITH base AS (
    SELECT
        cp.id_uuid AS clutch_plan_id,
        pc.id_uuid AS planned_cross_id,
        cp.clutch_code,
        cp.planned_name AS clutch_name,
        cp.planned_nickname AS clutch_nickname,
        pc.cross_date AS date_planned,
        cp.created_by,
        cp.created_at,
        coalesce(cp.note, pc.note) AS note
    FROM public.clutch_plans AS cp
    LEFT JOIN public.planned_crosses AS pc ON cp.id_uuid = pc.clutch_id
),

inst AS (
    SELECT
        c.planned_cross_id,
        count(*)::int AS n_instances,
        count(c.cross_id)::int AS n_crosses,
        max(c.date_birth) AS latest_date_birth
    FROM public.clutches AS c
    GROUP BY c.planned_cross_id
),

cont AS (
    SELECT
        c.planned_cross_id,
        count(cc.*)::int AS n_containers
    FROM public.clutches AS c
    INNER JOIN public.clutch_containers AS cc ON c.id_uuid = cc.clutch_id
    GROUP BY c.planned_cross_id
)

SELECT
    b.clutch_plan_id,
    b.planned_cross_id,
    b.clutch_code,
    b.clutch_name,
    b.clutch_nickname,
    b.date_planned,
    b.created_by,
    b.created_at,
    b.note,
    i.latest_date_birth,
    coalesce(i.n_instances, 0) AS n_instances,
    coalesce(coalesce(i.n_crosses, 0), 0) AS n_crosses,
    coalesce(ct.n_containers, 0) AS n_containers
FROM base AS b
LEFT JOIN inst AS i ON b.planned_cross_id = i.planned_cross_id
LEFT JOIN cont AS ct ON b.planned_cross_id = ct.planned_cross_id
ORDER BY coalesce(b.date_planned::timestamp, b.created_at) DESC NULLS LAST;

COMMIT;

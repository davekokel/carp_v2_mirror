BEGIN;

CREATE OR REPLACE VIEW public.v_planned_clutches_overview AS
WITH x AS (
    SELECT
        cp.id_uuid AS clutch_plan_id,
        pc.id_uuid AS planned_cross_id,
        cp.clutch_code,
        cp.planned_name AS clutch_name,
        cp.planned_nickname AS clutch_nickname,
        pc.cross_date,
        cp.created_by,
        cp.created_at,
        coalesce(cp.note, pc.note) AS note
    FROM public.clutch_plans AS cp
    LEFT JOIN public.planned_crosses AS pc ON cp.id_uuid = pc.clutch_id
),

tx AS (
    SELECT
        t.clutch_id AS clutch_plan_id,
        count(*)::int AS n_treatments
    FROM public.clutch_plan_treatments AS t
    GROUP BY 1
)

SELECT
    x.clutch_plan_id,
    x.planned_cross_id,
    x.clutch_code,
    x.clutch_name,
    x.clutch_nickname,
    x.cross_date,
    x.created_by,
    x.created_at,
    x.note,
    coalesce(tx.n_treatments, 0) AS n_treatments
FROM x
LEFT JOIN tx ON x.clutch_plan_id = tx.clutch_plan_id
ORDER BY coalesce(x.cross_date::timestamp, x.created_at) DESC NULLS LAST;

COMMIT;

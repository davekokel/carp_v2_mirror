BEGIN;

DROP VIEW IF EXISTS public.vw_clutches_overview_human;

CREATE VIEW public.vw_clutches_overview_human AS
WITH base AS (
    SELECT
        c.id_uuid AS clutch_id,
        c.date_birth,
        c.created_by,
        c.created_at,
        c.note,
        c.batch_label,
        c.seed_batch_id,
        c.planned_cross_id,
        cp.clutch_code,
        cp.planned_name AS clutch_name,
        c.cross_id,
        COALESCE(mt.label, mt.tank_code) AS mom_tank_label,
        COALESCE(ft.label, ft.tank_code) AS dad_tank_label
    FROM public.clutches AS c
    LEFT JOIN public.planned_crosses AS pc ON c.planned_cross_id = pc.id_uuid
    LEFT JOIN public.clutch_plans AS cp ON pc.clutch_id = cp.id_uuid
    LEFT JOIN public.containers AS mt ON pc.mother_tank_id = mt.id_uuid
    LEFT JOIN public.containers AS ft ON pc.father_tank_id = ft.id_uuid
),

instances AS (
    SELECT
        cc.clutch_id,
        COUNT(*)::int AS n_instances
    FROM public.clutch_containers AS cc
    GROUP BY cc.clutch_id
),

crosses_via_clutches AS (
    -- 1 if clutches.cross_id links to a crosses row, else 0
    SELECT
        b.clutch_id,
        COUNT(x.id_uuid)::int AS n_crosses
    FROM base AS b
    LEFT JOIN public.crosses AS x ON b.cross_id = x.id_uuid
    GROUP BY b.clutch_id
)

SELECT
    b.clutch_id,
    b.date_birth,
    b.created_by,
    b.created_at,
    b.note,
    b.batch_label,
    b.seed_batch_id,
    b.clutch_code,
    b.clutch_name,
    NULL::text AS clutch_nickname,
    b.mom_tank_label,
    b.dad_tank_label,
    COALESCE(i.n_instances, 0) AS n_instances,
    COALESCE(cx.n_crosses, 0) AS n_crosses
FROM base AS b
LEFT JOIN instances AS i ON b.clutch_id = i.clutch_id
LEFT JOIN crosses_via_clutches AS cx ON b.clutch_id = cx.clutch_id
ORDER BY COALESCE(b.date_birth::timestamp, b.created_at) DESC NULLS LAST;

COMMIT;

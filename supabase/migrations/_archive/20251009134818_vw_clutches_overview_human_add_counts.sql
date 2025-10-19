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
        coalesce(mt.label, mt.tank_code) AS mom_tank_label,
        coalesce(ft.label, ft.tank_code) AS dad_tank_label
    FROM public.clutches AS c
    LEFT JOIN public.planned_crosses AS pc ON c.planned_cross_id = pc.id_uuid
    LEFT JOIN public.clutch_plans AS cp ON pc.clutch_id = cp.id_uuid
    LEFT JOIN public.containers AS mt ON pc.mother_tank_id = mt.id_uuid
    LEFT JOIN public.containers AS ft ON pc.father_tank_id = ft.id_uuid
),

instances AS (
    SELECT
        cc.clutch_id,
        count(*)::int AS n_instances
    FROM public.clutch_containers AS cc
    GROUP BY cc.clutch_id
),

crosses_direct AS (
    -- if crosses carries clutch_id
    SELECT
        x.clutch_id,
        count(*)::int AS n_crosses
    FROM public.crosses AS x
    WHERE x.clutch_id IS NOT null
    GROUP BY x.clutch_id
),

crosses_via_clutches AS (
    -- otherwise: clutches.cross_id → crosses.id_uuid (1:1); count it as 1
    SELECT
        c.id_uuid AS clutch_id,
        count(x.id_uuid)::int AS n_crosses
    FROM public.clutches AS c
    LEFT JOIN public.crosses AS x ON c.cross_id = x.id_uuid
    GROUP BY c.id_uuid
),

crosses_union AS (
    SELECT
        clutch_id,
        sum(n_crosses)::int AS n_crosses
    FROM (
        SELECT * FROM crosses_direct
        UNION ALL
        SELECT * FROM crosses_via_clutches
    ) AS u
    GROUP BY clutch_id
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
    null::text AS clutch_nickname,
    b.mom_tank_label,
    b.dad_tank_label,
    coalesce(i.n_instances, 0) AS n_instances,
    coalesce(x.n_crosses, 0) AS n_crosses
FROM base AS b
LEFT JOIN instances AS i ON b.clutch_id = i.clutch_id
LEFT JOIN crosses_union AS x ON b.clutch_id = x.clutch_id
ORDER BY coalesce(b.date_birth::timestamp, b.created_at) DESC NULLS LAST;

COMMIT;

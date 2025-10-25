create or replace view public.v_cross_concepts_overview as
select
    v.clutch_code::text as conceptual_cross_code,
    v.clutch_code::text as clutch_code,         -- kept for compatibility
    coalesce(v.clutch_name, '')::text as name,
    coalesce(v.clutch_nickname, '')::text as nickname,
    coalesce(pc.mom_code, '')::text as mom_code,
    coalesce(pc.dad_code, '')::text as dad_code,
    coalesce(cm.tank_code, '')::text as mom_code_tank,
    coalesce(cd.tank_code, '')::text as dad_code_tank,
    coalesce(v.n_treatments, 0)::int as n_treatments,
    coalesce(v.created_by, '')::text as created_by,
    v.created_at::timestamptz as created_at
from public.v_planned_clutches_overview as v
left join public.planned_crosses as pc
    on v.clutch_code = pc.cross_code
left join public.containers as cm
    on pc.mother_tank_id = cm.id_uuid
left join public.containers as cd
    on pc.father_tank_id = cd.id_uuid;

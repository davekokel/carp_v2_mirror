-- Drop then recreate the view to add tank_pair_code.
drop view if exists public.v_tank_pairs_overview;

create view public.v_tank_pairs_overview as
select
    tp.id,
    tp.tank_pair_code,                                      -- NEW column
    tp.concept_id,
    tp.status,
    tp.created_by,
    tp.created_at,
    fp.id as fish_pair_id,
    mf.fish_code as mom_fish_code,
    df.fish_code as dad_fish_code,
    tp.mother_tank_id,
    mt.tank_code as mom_tank_code,
    tp.father_tank_id,
    dt.tank_code as dad_tank_code,
    coalesce(cp.clutch_code, cp.id::text) as clutch_code
from public.tank_pairs AS tp
inner join public.fish_pairs AS fp on tp.fish_pair_id = fp.id
inner join public.fish AS mf on fp.mom_fish_id = mf.id
inner join public.fish AS df on fp.dad_fish_id = df.id
left join public.clutch_plans AS cp on tp.concept_id = cp.id
inner join public.containers AS mt on tp.mother_tank_id = mt.id
inner join public.containers AS dt on tp.father_tank_id = dt.id;

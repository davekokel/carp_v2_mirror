\set ON_ERROR_STOP on
begin;

drop view if exists public.v_tank_pairs_overview cascade;

create view public.v_tank_pairs_overview as
with base as (
  select
    tp.id,
    tp.tank_pair_code,
    tp.concept_id,
    tp.fish_pair_id,
    tp.mother_tank_id,
    tp.father_tank_id,
    tp.status::text   as status,
    tp.created_by,
    tp.created_at
  from public.tank_pairs tp
),
concept as (
  select p.id::uuid as concept_id, coalesce(p.clutch_code, p.id::text) as clutch_code
  from public.clutch_plans p
),
fp as (
  select t.id::uuid as fish_pair_id, t.mom_fish_id, t.dad_fish_id
  from public.fish_pairs t
),
mom_fish as (
  select f.id as mom_fish_id, f.fish_code as mom_fish_code
  from public.fish f
),
dad_fish as (
  select f.id as dad_fish_id, f.fish_code as dad_fish_code
  from public.fish f
),
mtank as (
  select vt.tank_id::uuid as mother_tank_id, vt.tank_code::text as mom_tank_code, vt.status::text as mom_tank_status
  from public.v_tanks_for_fish vt
),
dtank as (
  select vt.tank_id::uuid as father_tank_id, vt.tank_code::text as dad_tank_code, vt.status::text as dad_tank_status
  from public.v_tanks_for_fish vt
)
select
  b.concept_id,
  b.mother_tank_id,
  b.father_tank_id,
  b.tank_pair_code,
  c.clutch_code,
  b.status,
  b.created_by,
  b.created_at,
  mf.mom_fish_code,
  mt.mom_tank_code,
  df.dad_fish_code,
  dt.dad_tank_code
from base b
left join concept  c   on c.concept_id      = b.concept_id
left join fp       f   on f.fish_pair_id    = b.fish_pair_id
left join mom_fish mf  on mf.mom_fish_id    = f.mom_fish_id
left join dad_fish df  on df.dad_fish_id    = f.dad_fish_id
left join mtank    mt  on mt.mother_tank_id = b.mother_tank_id
left join dtank    dt  on dt.father_tank_id = b.father_tank_id
order by b.created_at desc;

commit;

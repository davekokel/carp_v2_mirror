begin;

-- v_tank_pairs
-- Purpose: canonical read-model for recent/selected tank pairs, with clutch, fish, and tank codes.
-- Columns:
--   tank_pair_code, clutch_code, status, created_by, created_at,
--   mom_fish_code, mom_tank_code,
--   dad_fish_code, dad_tank_code
--
-- Sources:
--   tank_pairs            (concept_id, fish_pair_id, mother_tank_id, father_tank_id, status, created_by/at, optional tank_pair_code)
--   clutch_plans          (id → clutch_code)
--   fish_pairs            (id → mom_fish_id, dad_fish_id)
--   fish                  (id → fish_code)
--   v_tanks      (tank_id → tank_code/status; we join by tank_id, not fish)

create or replace view public.v_tank_pairs as
with base as (
  select
    tp.id,
    tp.tank_pair_code,
    tp.concept_id,
    tp.fish_pair_id,
    tp.mother_tank_id,
    tp.father_tank_id,
    tp.status,
    tp.created_by,
    tp.created_at
  from public.tank_pairs tp
),
concept as (
  select
    p.id::uuid                  as concept_id,
    coalesce(p.clutch_code, p.id::text) as clutch_code
  from public.clutch_plans p
),
fp as (
  select
    t.id::uuid                  as fish_pair_id,
    t.mom_fish_id,
    t.dad_fish_id
  from public.fish_pairs t
),
mom as (
  select f.id as mom_fish_id, f.fish_code as mom_fish_code
  from public.fish f
),
dad as (
  select f.id as dad_fish_id, f.fish_code as dad_fish_code
  from public.fish f
),
mtank as (
  select
    vt.tank_id::uuid           as mother_tank_id,
    vt.tank_code::text         as mom_tank_code,
    vt.status::text            as mom_tank_status
  from public.v_tanks vt
),
dtank as (
  select
    vt.tank_id::uuid           as father_tank_id,
    vt.tank_code::text         as dad_tank_code,
    vt.status::text            as dad_tank_status
  from public.v_tanks vt
)
select
  b.tank_pair_code,
  c.clutch_code,
  b.status,
  b.created_by,
  b.created_at,

  m.mom_fish_code,
  mt.mom_tank_code,

  d.dad_fish_code,
  dt.dad_tank_code

from base b
left join concept c on c.concept_id = b.concept_id
left join fp      f on f.fish_pair_id = b.fish_pair_id
left join mom     m on m.mom_fish_id  = f.mom_fish_id
left join dad     d on d.dad_fish_id  = f.dad_fish_id
left join mtank  mt on mt.mother_tank_id = b.mother_tank_id
left join dtank  dt on dt.father_tank_id = b.father_tank_id
order by b.created_at desc;

commit;

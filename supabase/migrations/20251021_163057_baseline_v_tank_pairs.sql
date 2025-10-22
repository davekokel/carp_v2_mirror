begin;

-- v_tank_pairs: readable pairing view expected by tank-centric migrations/pages
create or replace view public.v_tank_pairs as
select
  tp.id                           as tank_pair_id,
  tp.fish_pair_id,
  tp.mother_tank_id,
  tp.father_tank_id,
  coalesce(tp.tank_pair_code,'')  as tank_pair_code,
  coalesce(tp.status,'selected')  as status,
  tp.concept_id,
  tp.created_by,
  tp.created_at,

  -- labels/codes from v_tanks (mother)
  vm.label                        as mom_label,
  vm.tank_code                    as mom_tank_code,
  vm.fish_code                    as mom_fish_code,

  -- labels/codes from v_tanks (father)
  vf.label                        as dad_label,
  vf.tank_code                    as dad_tank_code,
  vf.fish_code                    as dad_fish_code

from public.tank_pairs tp
left join public.v_tanks vm on vm.tank_id = tp.mother_tank_id
left join public.v_tanks vf on vf.tank_id = tp.father_tank_id;

commit;

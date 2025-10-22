begin;

-- Ensure two demo fish exist
with upsert_fish as (
  insert into public.fish (fish_code, name, nickname, genetic_background, genotype, date_birth, created_by)
  values
    ('FSH-DEMO-001','demo 1','d1','casper','Tg(seed)gu1', current_date - 60, current_user),
    ('FSH-DEMO-002','demo 2','d2','casper','Tg(seed)gu2', current_date - 45, current_user)
  on conflict (fish_code) do update set updated_at = now()
  returning fish_code
)
select 1;

-- Ensure tanks for those fish (via containers baseline)
with f as (
  select id, fish_code from public.fish where fish_code in ('FSH-DEMO-001','FSH-DEMO-002')
),
ins as (
  insert into public.containers (id, label, fish_code, tank_code, status, created_by)
  select gen_random_uuid(), 'demo mother', 'FSH-DEMO-001',
         'TANK-FSH-DEMO-001-#1', 'new_tank', current_user
    where not exists (select 1 from public.containers where tank_code='TANK-FSH-DEMO-001-#1')
  union all
  select gen_random_uuid(), 'demo father', 'FSH-DEMO-002',
         'TANK-FSH-DEMO-002-#1', 'new_tank', current_user
    where not exists (select 1 from public.containers where tank_code='TANK-FSH-DEMO-002-#1')
)
select 1;

-- Optional: create a tank_pair + run so v_crosses/v_cross_runs show something
with mom as (select id as mom_tank_id from public.containers where tank_code='TANK-FSH-DEMO-001-#1' limit 1),
     dad as (select id as dad_tank_id from public.containers where tank_code='TANK-FSH-DEMO-002-#1' limit 1),
     tp  as (
       insert into public.tank_pairs (mother_tank_id, father_tank_id, tank_pair_code, status, created_by)
       select mom.mom_tank_id, dad.dad_tank_id, 'TP-SEED-0001', 'selected', current_user
       from mom, dad
       on conflict (mother_tank_id, father_tank_id) do update set updated_at=now()
       returning id
     )
insert into public.cross_instances (tank_pair_id, cross_run_code, cross_date, note, created_by)
select tp.id, 'CR-SEED-001', current_date, 'demo run', current_user
from tp
on conflict do nothing;

commit;

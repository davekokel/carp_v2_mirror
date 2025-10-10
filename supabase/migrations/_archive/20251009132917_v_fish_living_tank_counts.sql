BEGIN;

create or replace view public.v_fish_living_tank_counts as
select
  m.fish_id,
  count(*)::int as n_living_tanks
from public.fish_tank_memberships m
join public.containers c on c.id_uuid = m.container_id
where m.left_at is null
  and c.status in ('active','new_tank')
group by m.fish_id;

create index if not exists idx_ftm_fish_id on public.fish_tank_memberships(fish_id);

COMMIT;

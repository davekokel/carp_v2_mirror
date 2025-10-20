begin;

create or replace view public.v_tanks_for_fish as
select
  t.id as tank_id,
  t.tank_code,
  t.status,
  t.capacity,
  t.created_at as tank_created_at,
  t.updated_at as tank_updated_at,
  f.id as fish_id,
  f.fish_code
from public.tanks t
join public.fish f on f.id = t.fish_id;

create or replace function public.fn_set_tank_capacity(p_tank_id uuid, p_capacity int)
returns void
language plpgsql
as $$
begin
  update public.tanks
     set capacity=p_capacity, updated_at=now()
   where id=p_tank_id;
end
$$;

commit;

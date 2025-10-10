BEGIN;

create or replace view public.v_containers_live as
select *
from public.containers
where status in ('active','new_tank');

-- optional helper if you like function form
create or replace function public.is_container_live(s text)
returns boolean language sql immutable as $$
  select s in ('active','new_tank')
$$;

COMMIT;

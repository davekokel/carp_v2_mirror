begin;

do $$
begin
  if exists (
    select 1
    from pg_class c
    join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public' and c.relname='uniq_active_tank_per_fish'
  ) then
    drop index public.uniq_active_tank_per_fish;
  end if;
end$$;

create or replace function public.fn_set_tank_status(p_tank_id uuid, p_status public.tank_status)
returns text
language plpgsql
as $$
declare
  v_code text;
begin
  update public.tanks
     set status=p_status, updated_at=now()
   where id=p_tank_id
   returning tank_code into v_code;

  if v_code is null then
    raise exception 'tank % not found', p_tank_id;
  end if;

  return v_code;
end
$$;

commit;

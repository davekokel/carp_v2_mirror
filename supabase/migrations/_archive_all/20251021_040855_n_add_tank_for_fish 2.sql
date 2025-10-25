begin;

create or replace function public.fn_add_tank_for_fish(p_fish_id uuid, p_status public.tank_status default 'new_tank', p_capacity int default null)
returns text
language plpgsql
as $$
declare
  v_code text;
begin
  v_code := format('TANK-%s-#%s',
                   (select fish_code from public.fish where id=p_fish_id),
                   public.fn_next_tank_suffix(p_fish_id));

  insert into public.tanks (fish_id, tank_code, status, capacity)
  values (p_fish_id, v_code, p_status, p_capacity);

  return v_code;
end
$$;

commit;

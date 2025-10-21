do $$
declare
  has_fish_id boolean;
  has_assign  boolean;
begin
  select exists(
    select 1 from information_schema.columns
    where table_schema='public' and table_name='tanks' and column_name='fish_id'
  ) into has_fish_id;

  if has_fish_id then
    execute $SQL$
      create or replace view public.v_tanks_for_fish as
      select
        t.id          as tank_id,
        t.tank_code,
        t.status,
        t.capacity,
        t.created_at  as tank_created_at,
        t.updated_at  as tank_updated_at,
        f.id          as fish_id,
        f.fish_code
      from public.tanks t
      join public.fish f on f.id = t.fish_id;
    $SQL$;
  else
    select exists(
      select 1 from information_schema.tables
      where table_schema='public' and table_name='tank_assignments'
    ) into has_assign;

    if has_assign then
      execute $SQL$
        create or replace view public.v_tanks_for_fish as
        with latest as (
          select distinct on (t.id)
            t.id as tank_id,
            a.fish_id as fish_id
          from public.tanks t
          left join public.tank_assignments a on a.tank_id = t.id
          order by t.id, a.assigned_at desc nulls last
        )
        select
          t.id          as tank_id,
          t.tank_code,
          t.status,
          t.capacity,
          t.created_at  as tank_created_at,
          t.updated_at  as tank_updated_at,
          f.id          as fish_id,
          f.fish_code
        from public.tanks t
        left join latest l on l.tank_id = t.id
        left join public.fish f on f.id = l.fish_id;
      $SQL$;
    else
      execute $SQL$
        create or replace view public.v_tanks_for_fish as
        select
          t.id          as tank_id,
          t.tank_code,
          t.status,
          t.capacity,
          t.created_at  as tank_created_at,
          t.updated_at  as tank_updated_at,
          null::uuid    as fish_id,
          null::text    as fish_code
        from public.tanks t;
      $SQL$;
    end if;
  end if;
end$$;

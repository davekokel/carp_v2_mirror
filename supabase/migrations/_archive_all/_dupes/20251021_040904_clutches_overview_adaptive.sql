do $$
begin
  if exists (
    select 1 from pg_views
    where schemaname='public' and viewname='v_clutch_instances_overview'
  ) then
    execute $V$
      create or replace view public.v_clutches_overview as
      select
        cio.clutch_instance_code::text     as clutch_code,
        cio.cross_instance_code::text      as cross_code,
        cio.lay_date::date                 as lay_date,
        cio.n_eggs::int                    as n_eggs,
        cio.n_hatched::int                 as n_hatched,
        cio.created_at::timestamptz        as created_at
      from public.v_clutch_instances_overview cio;
    $V$;
  else
    execute $V$
      create or replace view public.v_clutches_overview as
      select
        null::text         as clutch_code,
        null::text         as cross_code,
        null::date         as lay_date,
        null::int          as n_eggs,
        null::int          as n_hatched,
        null::timestamptz  as created_at
      where false;
    $V$;
  end if;
end$$;

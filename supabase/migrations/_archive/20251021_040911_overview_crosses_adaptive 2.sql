do $$
begin
  if exists (
    select 1 from information_schema.tables
    where table_schema='public' and table_name='cross_instances'
  ) then
    execute $V$
      create or replace view public.v_overview_crosses as
      select
        ci.created_at::timestamptz           as created_at,
        ci.cross_instance_code::text         as cross_code,
        ci.status::text                      as status,
        ci.mother_tank_id::uuid              as mother_tank_id,
        ci.father_tank_id::uuid              as father_tank_id,
        vt_m.tank_code::text                 as mother_tank_code,
        vt_f.tank_code::text                 as father_tank_code
      from public.cross_instances ci
      left join public.v_tanks vt_m on vt_m.tank_id = ci.mother_tank_id
      left join public.v_tanks vt_f on vt_f.tank_id = ci.father_tank_id;
    $V$;
  elsif exists (
    select 1 from information_schema.tables
    where table_schema='public' and table_name='planned_crosses'
  ) then
    execute $V$
      create or replace view public.v_overview_crosses as
      select
        pc.created_at::timestamptz           as created_at,
        pc.planned_cross_code::text          as cross_code,
        coalesce(pc.status::text,'')         as status,
        pc.mother_tank_id::uuid              as mother_tank_id,
        pc.father_tank_id::uuid              as father_tank_id,
        vt_m.tank_code::text                 as mother_tank_code,
        vt_f.tank_code::text                 as father_tank_code
      from public.planned_crosses pc
      left join public.v_tanks vt_m on vt_m.tank_id = pc.mother_tank_id
      left join public.v_tanks vt_f on vt_f.tank_id = pc.father_tank_id;
    $V$;
  else
    execute $V$
      create or replace view public.v_overview_crosses as
      select
        null::timestamptz  as created_at,
        null::text         as cross_code,
        null::text         as status,
        null::uuid         as mother_tank_id,
        null::uuid         as father_tank_id,
        null::text         as mother_tank_code,
        null::text         as father_tank_code
      where false;
    $V$;
  end if;
end$$;

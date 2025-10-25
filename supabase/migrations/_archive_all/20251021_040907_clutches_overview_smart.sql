do $$
declare
  has_base boolean;
  -- chosen columns (identifiers) from v_clutch_instances_overview
  c_clutch text;
  c_cross  text;
  c_lay    text;
  c_eggs   text;
  c_hat    text;
  c_created text;
  q text;
  function pick(first text, second text, third text default null) returns text language plpgsql as $f$
  declare r text;
  begin
    for r in
      select c.column_name
      from information_schema.columns c
      where c.table_schema='public' and c.table_name='v_clutch_instances_overview'
        and c.column_name in (first, second, third)
      order by case c.column_name
                 when first then 1
                 when second then 2
                 when third then 3
               end
      limit 1
    loop
      return r;
    end loop;
    return null;
  end
  $f$;
begin
  has_base := exists (
    select 1 from pg_views
    where schemaname='public' and viewname='v_clutch_instances_overview'
  );

  if not has_base then
    execute $V$
      create or replace view public.v_clutches_overview as
      select
        null::text        as clutch_code,
        null::text        as cross_code,
        null::date        as lay_date,
        null::int         as n_eggs,
        null::int         as n_hatched,
        null::timestamptz as created_at
      where false;
    $V$;
    return;
  end if;

  -- pick best-available column names from v_clutch_instances_overview
  c_clutch  := pick('clutch_instance_code','clutch_code','clutch_id');
  c_cross   := pick('cross_instance_code','cross_code','cross_id');
  c_lay     := pick('lay_date','date_laid','laid_at');
  c_eggs    := pick('n_eggs','eggs_count','eggs');
  c_hat     := pick('n_hatched','hatched_count','hatched');
  c_created := pick('created_at','inserted_at','time_created');

  -- build CREATE VIEW using discovered columns (any NULLs get literal NULLs)
  q := format($FMT$
    create or replace view public.v_clutches_overview as
    select
      %s as clutch_code,
      %s as cross_code,
      %s as lay_date,
      %s as n_eggs,
      %s as n_hatched,
      %s as created_at
    from public.v_clutch_instances_overview
  $FMT$,
    coalesce(format('%s::text',    quote_ident(c_clutch)),  'null::text'),
    coalesce(format('%s::text',    quote_ident(c_cross)),   'null::text'),
    coalesce(format('%s::date',    quote_ident(c_lay)),     'null::date'),
    coalesce(format('%s::int',     quote_ident(c_eggs)),    'null::int'),
    coalesce(format('%s::int',     quote_ident(c_hat)),     'null::int'),
    coalesce(format('%s::timestamptz', quote_ident(c_created)), 'null::timestamptz')
  );

  execute q;
end$$;

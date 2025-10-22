do $do$
declare
  has_base boolean;
  c_clutch  text;
  c_cross   text;
  c_lay     text;
  c_eggs    text;
  c_hat     text;
  c_created text;
  expr_clutch  text;
  expr_cross   text;
  expr_lay     text;
  expr_eggs    text;
  expr_hat     text;
  expr_created text;
  q text;
begin
  -- is the source view present?
  select exists(
    select 1 from pg_views where schemaname='public' and viewname='v_clutch_instances_overview'
  ) into has_base;

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

  -- pick first existing column among preferred candidates
  with prefs(col) as (
    values ('clutch_instance_code'),('clutch_code'),('clutch_id')
  )
  select p.col
  into c_clutch
  from prefs p
  where exists (
    select 1 from information_schema.columns c
    where c.table_schema='public' and c.table_name='v_clutch_instances_overview' and c.column_name=p.col
  )
  limit 1;

  with prefs(col) as (
    values ('cross_instance_code'),('cross_code'),('cross_id')
  )
  select p.col
  into c_cross
  from prefs p
  where exists (
    select 1 from information_schema.columns c
    where c.table_schema='public' and c.table_name='v_clutch_instances_overview' and c.column_name=p.col
  )
  limit 1;

  with prefs(col) as ( values ('lay_date'),('date_laid'),('laid_at') )
  select p.col into c_lay
  from prefs p
  where exists (select 1 from information_schema.columns c
                where c.table_schema='public' and c.table_name='v_clutch_instances_overview' and c.column_name=p.col)
  limit 1;

  with prefs(col) as ( values ('n_eggs'),('eggs_count'),('eggs') )
  select p.col into c_eggs
  from prefs p
  where exists (select 1 from information_schema.columns c
                where c.table_schema='public' and c.table_name='v_clutch_instances_overview' and c.column_name=p.col)
  limit 1;

  with prefs(col) as ( values ('n_hatched'),('hatched_count'),('hatched') )
  select p.col into c_hat
  from prefs p
  where exists (select 1 from information_schema.columns c
                where c.table_schema='public' and c.table_name='v_clutch_instances_overview' and c.column_name=p.col)
  limit 1;

  with prefs(col) as ( values ('created_at'),('inserted_at'),('time_created') )
  select p.col into c_created
  from prefs p
  where exists (select 1 from information_schema.columns c
                where c.table_schema='public' and c.table_name='v_clutch_instances_overview' and c.column_name=p.col)
  limit 1;

  -- build select expressions (fallback to NULL typed)
  expr_clutch  := case when c_clutch  is null then 'null::text'        else quote_ident(c_clutch)  || '::text'        end;
  expr_cross   := case when c_cross   is null then 'null::text'        else quote_ident(c_cross)   || '::text'        end;
  expr_lay     := case when c_lay     is null then 'null::date'        else quote_ident(c_lay)     || '::date'        end;
  expr_eggs    := case when c_eggs    is null then 'null::int'         else quote_ident(c_eggs)    || '::int'         end;
  expr_hat     := case when c_hat     is null then 'null::int'         else quote_ident(c_hat)     || '::int'         end;
  expr_created := case when c_created is null then 'null::timestamptz' else quote_ident(c_created) || '::timestamptz' end;

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
  $FMT$, expr_clutch, expr_cross, expr_lay, expr_eggs, expr_hat, expr_created);

  execute q;
end
$do$;

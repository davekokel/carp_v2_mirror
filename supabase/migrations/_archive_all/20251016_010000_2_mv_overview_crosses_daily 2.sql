begin;
drop materialized view if exists public.mv_overview_crosses_daily;
create materialized view public.mv_overview_crosses_daily as
select
    ci.cross_date::date as run_day,
    COUNT(*) as runs_count,
    COUNT(distinct pc.clutch_id) as clutches_count,
    MAX(ci.cross_date) as last_run_date
from public.cross_instances AS ci
inner join public.planned_crosses AS pc on ci.cross_id = pc.cross_id
group by run_day
order by run_day desc
with no data;
create unique index if not exists ux_mv_overview_crosses_daily_day on public.mv_overview_crosses_daily (run_day);
refresh materialized view public.mv_overview_crosses_daily;
create or replace function public.refresh_mv_overview_crosses_daily()
returns trigger language plpgsql as $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_crosses_daily;
  RETURN NULL;
END
$$;
drop trigger if exists trg_refresh_mv_overview_crosses_daily_i on public.cross_instances;
drop trigger if exists trg_refresh_mv_overview_crosses_daily_u on public.cross_instances;
drop trigger if exists trg_refresh_mv_overview_crosses_daily_d on public.cross_instances;
create trigger trg_refresh_mv_overview_crosses_daily_i after insert on public.cross_instances for each statement execute function public.refresh_mv_overview_crosses_daily();
create trigger trg_refresh_mv_overview_crosses_daily_u after update on public.cross_instances for each statement execute function public.refresh_mv_overview_crosses_daily();
create trigger trg_refresh_mv_overview_crosses_daily_d after delete on public.cross_instances for each statement execute function public.refresh_mv_overview_crosses_daily();
commit;

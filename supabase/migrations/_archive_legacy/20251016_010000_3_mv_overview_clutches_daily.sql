begin;
drop materialized view if exists public.mv_overview_clutches_daily;
create materialized view public.mv_overview_clutches_daily as
select
    COALESCE(ci.annotated_at::date, ci.created_at::date) as annot_day,
    COUNT(*) as annotations_count,
    MAX(COALESCE(ci.annotated_at, ci.created_at)) as last_annotated
from public.clutch_instances AS ci
group by annot_day
order by annot_day desc
with no data;
create unique index if not exists ux_mv_overview_clutches_daily_day on public.mv_overview_clutches_daily (annot_day);
refresh materialized view public.mv_overview_clutches_daily;
create or replace function public.refresh_mv_overview_clutches_daily()
returns trigger language plpgsql as $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_clutches_daily;
  RETURN NULL;
END
$$;
drop trigger if exists trg_refresh_mv_overview_clutches_daily_i on public.clutch_instances;
drop trigger if exists trg_refresh_mv_overview_clutches_daily_u on public.clutch_instances;
drop trigger if exists trg_refresh_mv_overview_clutches_daily_d on public.clutch_instances;
create trigger trg_refresh_mv_overview_clutches_daily_i after insert on public.clutch_instances for each statement execute function public.refresh_mv_overview_clutches_daily();
create trigger trg_refresh_mv_overview_clutches_daily_u after update on public.clutch_instances for each statement execute function public.refresh_mv_overview_clutches_daily();
create trigger trg_refresh_mv_overview_clutches_daily_d after delete on public.clutch_instances for each statement execute function public.refresh_mv_overview_clutches_daily();
commit;

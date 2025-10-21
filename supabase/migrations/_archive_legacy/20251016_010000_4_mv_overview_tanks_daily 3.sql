begin;

drop materialized view if exists public.mv_overview_tanks_daily;
create materialized view public.mv_overview_tanks_daily as
with base as (
    select
        c.created_at::date as tank_day,
        c.id,
        c.status,
        c.activated_at,
        c.last_seen_at,
        c.created_at
    from public.containers AS c
    where c.container_type in ('inventory_tank', 'holding_tank', 'nursery_tank')
)

select
    tank_day,
    COUNT(*) as tanks_created,
    SUM(case when status = 'active' then 1 else 0 end) as active_count,
    SUM(case when activated_at::date = tank_day then 1 else 0 end) as activated_count,
    MAX(last_seen_at) as last_seen_at,
    MAX(created_at) as last_created
from base  group by tank_day
order by tank_day desc
with no data;

create unique index if not exists ux_mv_overview_tanks_daily_day
on public.mv_overview_tanks_daily (tank_day);
create index if not exists ix_mv_overview_tanks_daily_lastseen
on public.mv_overview_tanks_daily (last_seen_at desc);

refresh materialized view public.mv_overview_tanks_daily;

create or replace function public.refresh_mv_overview_tanks_daily()
returns trigger language plpgsql as $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_tanks_daily;
  RETURN NULL;
END
$$;

drop trigger if exists trg_refresh_mv_overview_tanks_daily_i on public.containers;
drop trigger if exists trg_refresh_mv_overview_tanks_daily_u on public.containers;
drop trigger if exists trg_refresh_mv_overview_tanks_daily_d on public.containers;

create trigger trg_refresh_mv_overview_tanks_daily_i
after insert on public.containers
for each statement execute function public.refresh_mv_overview_tanks_daily();

create trigger trg_refresh_mv_overview_tanks_daily_u
after update on public.containers
for each statement execute function public.refresh_mv_overview_tanks_daily();

create trigger trg_refresh_mv_overview_tanks_daily_d
after delete on public.containers
for each statement execute function public.refresh_mv_overview_tanks_daily();

commit;

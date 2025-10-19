begin;

drop materialized view if exists public.mv_overview_plasmids_daily;
create materialized view public.mv_overview_plasmids_daily as
select
    p.created_at::date as plasmid_day,
    COUNT(*) as plasmids_created,
    MAX(p.created_at) as last_created
from public.plasmids AS p
group by plasmid_day
order by plasmid_day desc
with no data;

create unique index if not exists ux_mv_overview_plasmids_daily_day
on public.mv_overview_plasmids_daily (plasmid_day);

refresh materialized view public.mv_overview_plasmids_daily;

create or replace function public.refresh_mv_overview_plasmids_daily()
returns trigger language plpgsql as $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_plasmids_daily;
  RETURN NULL;
END
$$;

drop trigger if exists trg_refresh_mv_overview_plasmids_daily_i on public.plasmids;
drop trigger if exists trg_refresh_mv_overview_plasmids_daily_u on public.plasmids;
drop trigger if exists trg_refresh_mv_overview_plasmids_daily_d on public.plasmids;

create trigger trg_refresh_mv_overview_plasmids_daily_i
after insert on public.plasmids
for each statement execute function public.refresh_mv_overview_plasmids_daily();

create trigger trg_refresh_mv_overview_plasmids_daily_u
after update on public.plasmids
for each statement execute function public.refresh_mv_overview_plasmids_daily();

create trigger trg_refresh_mv_overview_plasmids_daily_d
after delete on public.plasmids
for each statement execute function public.refresh_mv_overview_plasmids_daily();

commit;

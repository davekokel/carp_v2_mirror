begin;

drop materialized view if exists public.mv_overview_fish_daily;
create materialized view public.mv_overview_fish_daily as
select
    f.created_at::date as fish_day,
    COUNT(*) as fish_created,
    SUM(case when f.date_birth = f.created_at::date then 1 else 0 end) as births_logged,
    MAX(f.created_at) as last_created
from public.fish AS f
group by fish_day
order by fish_day desc
with no data;

create unique index if not exists ux_mv_overview_fish_daily_day
on public.mv_overview_fish_daily (fish_day);

refresh materialized view public.mv_overview_fish_daily;

create or replace function public.refresh_mv_overview_fish_daily()
returns trigger language plpgsql as $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_fish_daily;
  RETURN NULL;
END
$$;

drop trigger if exists trg_refresh_mv_overview_fish_daily_i on public.fish;
drop trigger if exists trg_refresh_mv_overview_fish_daily_u on public.fish;
drop trigger if exists trg_refresh_mv_overview_fish_daily_d on public.fish;

create trigger trg_refresh_mv_overview_fish_daily_i
after insert on public.fish
for each statement execute function public.refresh_mv_overview_fish_daily();

create trigger trg_refresh_mv_overview_fish_daily_u
after update on public.fish
for each statement execute function public.refresh_mv_overview_fish_daily();

create trigger trg_refresh_mv_overview_fish_daily_d
after delete on public.fish
for each statement execute function public.refresh_mv_overview_fish_daily();

commit;

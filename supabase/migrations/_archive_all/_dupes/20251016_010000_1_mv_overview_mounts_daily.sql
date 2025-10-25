begin;
create index if not exists ix_mounts_date on public.mounts (mount_date);
create index if not exists ix_mounts_run on public.mounts (cross_instance_id);
create index if not exists ix_ci_cross_id on public.cross_instances (cross_id);
create index if not exists ix_pc_clutch_cross on public.planned_crosses (clutch_id, cross_id);
create index if not exists ix_cp_id_code on public.clutch_plans (id, clutch_code);
drop materialized view if exists public.mv_overview_mounts_daily;
create materialized view public.mv_overview_mounts_daily as
with base as (
    select
        m.mount_date::date as mount_day,
        m.id as mount_id,
        m.cross_instance_id,
        m.mounting_orientation as orientation,
        m.time_mounted,
        m.created_at,
        COALESCE(m.n_top, 0) as n_top,
        COALESCE(m.n_bottom, 0) as n_bottom
    from public.mounts AS m
),

ctx as (
    select
        b.*,
        cp.clutch_code
    from base AS b
    inner join public.cross_instances AS ci on b.cross_instance_id = ci.id
    inner join public.planned_crosses AS pc on ci.cross_id = pc.cross_id
    inner join public.clutch_plans AS cp on pc.clutch_id = cp.id
),

hist as (
    select
        mount_day,
        orientation,
        COUNT(*) as cnt
    from ctx  group by mount_day, orientation
)

select
    mount_day,
    COUNT(*) as mounts_count,
    SUM(n_top + n_bottom) as embryos_total_sum,
    COUNT(distinct cross_instance_id) as runs_count,
    COUNT(distinct clutch_code) as clutches_count,
    COALESCE(JSONB_OBJECT_AGG(orientation, cnt) filter (where orientation is not NULL), '{}'::jsonb)
        as orientations_json,
    MAX(time_mounted) as last_time_mounted
from ctx  left join hist AS on ctx.mount_day = hist.mount_day and ctx.orientation = hist.orientation
group by mount_day
order by mount_day desc
with no data;
create unique index if not exists ux_mv_overview_mounts_daily_day on public.mv_overview_mounts_daily (mount_day);
create index if not exists ix_mv_overview_mounts_daily_lasttime on public.mv_overview_mounts_daily (
    last_time_mounted desc
);
refresh materialized view public.mv_overview_mounts_daily;
create or replace function public.refresh_mv_overview_mounts_daily()
returns trigger language plpgsql as $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_mounts_daily;
  RETURN NULL;
END
$$;
drop trigger if exists trg_refresh_mv_overview_mounts_daily_ins on public.mounts;
drop trigger if exists trg_refresh_mv_overview_mounts_daily_upd on public.mounts;
drop trigger if exists trg_refresh_mv_overview_mounts_daily_del on public.mounts;
create trigger trg_refresh_mv_overview_mounts_daily_ins after insert on public.mounts for each statement execute function public.refresh_mv_overview_mounts_daily();
create trigger trg_refresh_mv_overview_mounts_daily_upd after update on public.mounts for each statement execute function public.refresh_mv_overview_mounts_daily();
create trigger trg_refresh_mv_overview_mounts_daily_del after delete on public.mounts for each statement execute function public.refresh_mv_overview_mounts_daily();
commit;

BEGIN;
CREATE INDEX IF NOT EXISTS ix_mounts_date ON public.mounts(mount_date);
CREATE INDEX IF NOT EXISTS ix_mounts_run ON public.mounts(cross_instance_id);
CREATE INDEX IF NOT EXISTS ix_ci_cross_id ON public.cross_instances(cross_id);
CREATE INDEX IF NOT EXISTS ix_pc_clutch_cross ON public.planned_crosses(clutch_id, cross_id);
CREATE INDEX IF NOT EXISTS ix_cp_id_code ON public.clutch_plans(id, clutch_code);
DROP MATERIALIZED VIEW IF EXISTS public.mv_overview_mounts_daily;
CREATE MATERIALIZED VIEW public.mv_overview_mounts_daily AS
WITH base AS (
  SELECT
    m.mount_date::date AS mount_day,
    m.id AS mount_id,
    m.cross_instance_id,
    COALESCE(m.n_top,0) AS n_top,
    COALESCE(m.n_bottom,0) AS n_bottom,
    m.mounting_orientation AS orientation,
    m.time_mounted,
    m.created_at
  FROM public.mounts m
),
ctx AS (
  SELECT
    b.*,
    cp.clutch_code
  FROM base b
  JOIN public.cross_instances ci ON ci.id = b.cross_instance_id
  JOIN public.planned_crosses pc ON pc.cross_id = ci.cross_id
  JOIN public.clutch_plans cp ON cp.id = pc.clutch_id
)
SELECT
  mount_day,
  COUNT(*) AS mounts_count,
  SUM(n_top + n_bottom) AS embryos_total_sum,
  COUNT(DISTINCT cross_instance_id) AS runs_count,
  COUNT(DISTINCT clutch_code) AS clutches_count,
  COALESCE(jsonb_object_agg(orientation, cnt) FILTER (WHERE orientation IS NOT NULL), '{}'::jsonb) AS orientations_json,
  MAX(time_mounted) AS last_time_mounted
FROM ctx
LEFT JOIN (
  SELECT mount_day, orientation, COUNT(*) AS cnt
  FROM ctx
  GROUP BY mount_day, orientation
) hist ON hist.mount_day = ctx.mount_day AND hist.orientation = ctx.orientation
GROUP BY mount_day
ORDER BY mount_day DESC
WITH NO DATA;
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_overview_mounts_daily_day ON public.mv_overview_mounts_daily(mount_day);
CREATE INDEX IF NOT EXISTS ix_mv_overview_mounts_daily_lasttime ON public.mv_overview_mounts_daily(last_time_mounted DESC);
REFRESH MATERIALIZED VIEW public.mv_overview_mounts_daily;
CREATE OR REPLACE FUNCTION public.refresh_mv_overview_mounts_daily()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_mounts_daily;
  RETURN NULL;
END
$$;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_mounts_daily_ins ON public.mounts;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_mounts_daily_upd ON public.mounts;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_mounts_daily_del ON public.mounts;
CREATE TRIGGER trg_refresh_mv_overview_mounts_daily_ins AFTER INSERT ON public.mounts FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_mounts_daily();
CREATE TRIGGER trg_refresh_mv_overview_mounts_daily_upd AFTER UPDATE ON public.mounts FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_mounts_daily();
CREATE TRIGGER trg_refresh_mv_overview_mounts_daily_del AFTER DELETE ON public.mounts FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_mounts_daily();
COMMIT;

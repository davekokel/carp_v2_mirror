BEGIN;

DROP MATERIALIZED VIEW IF EXISTS public.mv_overview_tanks_daily;
CREATE MATERIALIZED VIEW public.mv_overview_tanks_daily AS
WITH base AS (
  SELECT
    c.created_at::date              AS tank_day,
    c.id,
    c.status,
    c.activated_at,
    c.last_seen_at,
    c.created_at
  FROM public.containers c
  WHERE c.container_type IN ('inventory_tank','holding_tank','nursery_tank')
)
SELECT
  tank_day,
  COUNT(*)                                                   AS tanks_created,
  SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END)        AS active_count,
  SUM(CASE WHEN activated_at::date = tank_day THEN 1 ELSE 0 END) AS activated_count,
  MAX(last_seen_at)                                         AS last_seen_at,
  MAX(created_at)                                           AS last_created
FROM base
GROUP BY tank_day
ORDER BY tank_day DESC
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_overview_tanks_daily_day
  ON public.mv_overview_tanks_daily(tank_day);
CREATE INDEX IF NOT EXISTS ix_mv_overview_tanks_daily_lastseen
  ON public.mv_overview_tanks_daily(last_seen_at DESC);

REFRESH MATERIALIZED VIEW public.mv_overview_tanks_daily;

CREATE OR REPLACE FUNCTION public.refresh_mv_overview_tanks_daily()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_tanks_daily;
  RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS trg_refresh_mv_overview_tanks_daily_i ON public.containers;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_tanks_daily_u ON public.containers;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_tanks_daily_d ON public.containers;

CREATE TRIGGER trg_refresh_mv_overview_tanks_daily_i
AFTER INSERT ON public.containers
FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_tanks_daily();

CREATE TRIGGER trg_refresh_mv_overview_tanks_daily_u
AFTER UPDATE ON public.containers
FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_tanks_daily();

CREATE TRIGGER trg_refresh_mv_overview_tanks_daily_d
AFTER DELETE ON public.containers
FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_tanks_daily();

COMMIT;

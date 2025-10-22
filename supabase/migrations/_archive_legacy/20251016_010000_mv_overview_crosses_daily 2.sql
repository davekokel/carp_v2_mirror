BEGIN;
DROP MATERIALIZED VIEW IF EXISTS public.mv_overview_crosses_daily;
CREATE MATERIALIZED VIEW public.mv_overview_crosses_daily AS
SELECT
  ci.cross_date::date AS run_day,
  COUNT(*) AS runs_count,
  COUNT(DISTINCT pc.clutch_id) AS clutches_count,
  MAX(ci.cross_date) AS last_run_date
FROM public.cross_instances ci
JOIN public.planned_crosses pc ON pc.cross_id = ci.cross_id
GROUP BY run_day
ORDER BY run_day DESC
WITH NO DATA;
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_overview_crosses_daily_day ON public.mv_overview_crosses_daily(run_day);
REFRESH MATERIALIZED VIEW public.mv_overview_crosses_daily;
CREATE OR REPLACE FUNCTION public.refresh_mv_overview_crosses_daily()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_crosses_daily;
  RETURN NULL;
END
$$;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_crosses_daily_i ON public.cross_instances;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_crosses_daily_u ON public.cross_instances;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_crosses_daily_d ON public.cross_instances;
CREATE TRIGGER trg_refresh_mv_overview_crosses_daily_i AFTER INSERT ON public.cross_instances FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_crosses_daily();
CREATE TRIGGER trg_refresh_mv_overview_crosses_daily_u AFTER UPDATE ON public.cross_instances FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_crosses_daily();
CREATE TRIGGER trg_refresh_mv_overview_crosses_daily_d AFTER DELETE ON public.cross_instances FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_crosses_daily();
COMMIT;

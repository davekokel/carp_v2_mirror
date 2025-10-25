BEGIN;
DROP MATERIALIZED VIEW IF EXISTS public.mv_overview_clutches_daily;
CREATE MATERIALIZED VIEW public.mv_overview_clutches_daily AS
SELECT
  COALESCE(ci.annotated_at::date, ci.created_at::date) AS annot_day,
  COUNT(*) AS annotations_count,
  MAX(COALESCE(ci.annotated_at, ci.created_at)) AS last_annotated
FROM public.clutch_instances ci
GROUP BY annot_day
ORDER BY annot_day DESC
WITH NO DATA;
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_overview_clutches_daily_day ON public.mv_overview_clutches_daily(annot_day);
REFRESH MATERIALIZED VIEW public.mv_overview_clutches_daily;
CREATE OR REPLACE FUNCTION public.refresh_mv_overview_clutches_daily()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_clutches_daily;
  RETURN NULL;
END
$$;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_clutches_daily_i ON public.clutch_instances;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_clutches_daily_u ON public.clutch_instances;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_clutches_daily_d ON public.clutch_instances;
CREATE TRIGGER trg_refresh_mv_overview_clutches_daily_i AFTER INSERT ON public.clutch_instances FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_clutches_daily();
CREATE TRIGGER trg_refresh_mv_overview_clutches_daily_u AFTER UPDATE ON public.clutch_instances FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_clutches_daily();
CREATE TRIGGER trg_refresh_mv_overview_clutches_daily_d AFTER DELETE ON public.clutch_instances FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_clutches_daily();
COMMIT;

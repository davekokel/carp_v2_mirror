BEGIN;

DROP MATERIALIZED VIEW IF EXISTS public.mv_overview_plasmids_daily;
CREATE MATERIALIZED VIEW public.mv_overview_plasmids_daily AS
SELECT
  p.created_at::date                 AS plasmid_day,
  COUNT(*)                           AS plasmids_created,
  MAX(p.created_at)                  AS last_created
FROM public.plasmids p
GROUP BY plasmid_day
ORDER BY plasmid_day DESC
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_overview_plasmids_daily_day
  ON public.mv_overview_plasmids_daily(plasmid_day);

REFRESH MATERIALIZED VIEW public.mv_overview_plasmids_daily;

CREATE OR REPLACE FUNCTION public.refresh_mv_overview_plasmids_daily()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_plasmids_daily;
  RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS trg_refresh_mv_overview_plasmids_daily_i ON public.plasmids;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_plasmids_daily_u ON public.plasmids;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_plasmids_daily_d ON public.plasmids;

CREATE TRIGGER trg_refresh_mv_overview_plasmids_daily_i
AFTER INSERT ON public.plasmids
FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_plasmids_daily();

CREATE TRIGGER trg_refresh_mv_overview_plasmids_daily_u
AFTER UPDATE ON public.plasmids
FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_plasmids_daily();

CREATE TRIGGER trg_refresh_mv_overview_plasmids_daily_d
AFTER DELETE ON public.plasmids
FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_plasmids_daily();

COMMIT;

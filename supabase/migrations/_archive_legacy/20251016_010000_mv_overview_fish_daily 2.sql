BEGIN;

DROP MATERIALIZED VIEW IF EXISTS public.mv_overview_fish_daily;
CREATE MATERIALIZED VIEW public.mv_overview_fish_daily AS
SELECT
  f.created_at::date                                  AS fish_day,
  COUNT(*)                                            AS fish_created,
  SUM(CASE WHEN f.date_birth = f.created_at::date THEN 1 ELSE 0 END) AS births_logged,
  MAX(f.created_at)                                   AS last_created
FROM public.fish f
GROUP BY fish_day
ORDER BY fish_day DESC
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_overview_fish_daily_day
  ON public.mv_overview_fish_daily(fish_day);

REFRESH MATERIALIZED VIEW public.mv_overview_fish_daily;

CREATE OR REPLACE FUNCTION public.refresh_mv_overview_fish_daily()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_fish_daily;
  RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS trg_refresh_mv_overview_fish_daily_i ON public.fish;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_fish_daily_u ON public.fish;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_fish_daily_d ON public.fish;

CREATE TRIGGER trg_refresh_mv_overview_fish_daily_i
AFTER INSERT ON public.fish
FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_fish_daily();

CREATE TRIGGER trg_refresh_mv_overview_fish_daily_u
AFTER UPDATE ON public.fish
FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_fish_daily();

CREATE TRIGGER trg_refresh_mv_overview_fish_daily_d
AFTER DELETE ON public.fish
FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_fish_daily();

COMMIT;

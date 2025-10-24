BEGIN;

-- Drop if someone re-created it differently
DROP MATERIALIZED VIEW IF EXISTS public.mv_overview_tanks_daily;

-- Tanks-only daily rollup (no containers; relies on v_tanks shape)
-- v_tanks must expose: tank_id, tank_code, status, tank_created_at, fish_code
CREATE MATERIALIZED VIEW public.mv_overview_tanks_daily AS
WITH src AS (
  SELECT
    (date_trunc('day', v.tank_created_at))::date AS day,
    v.status::text                               AS status,
    NULLIF(TRIM(v.fish_code), '')                AS fish_code
  FROM public.v_tanks v
)
SELECT
  day,
  COUNT(*)                                   AS tanks_total,
  COUNT(*) FILTER (WHERE status = 'active')  AS tanks_active,
  COUNT(*) FILTER (WHERE status = 'new')     AS tanks_new,
  COUNT(*) FILTER (WHERE status NOT IN ('active','new') OR status IS NULL) AS tanks_other,
  COUNT(DISTINCT fish_code)                  AS fish_with_tanks
FROM src
GROUP BY day
ORDER BY day;

-- Nice-to-have index for time-bounded queries
CREATE INDEX IF NOT EXISTS mv_overview_tanks_daily_day_idx
  ON public.mv_overview_tanks_daily (day);

COMMIT;

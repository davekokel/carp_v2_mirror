BEGIN;

-- 1) Helpful index for CI → groups
CREATE INDEX IF NOT EXISTS ix_treated_clutches_ci
  ON public.treated_clutches (clutch_instance_id);

-- 2) Backfill a baseline untreated group "T(<clutch_code>)-0" for every clutch that lacks one
WITH base AS (
  SELECT
    ci.id                         AS clutch_id,
    ci.clutch_instance_code       AS clutch_code,
    ci.created_at                 AS clutch_created_at,
    'T('||ci.clutch_instance_code||')-0' AS baseline_code
  FROM public.clutch_instances ci
),
missing AS (
  SELECT b.*
  FROM base b
  LEFT JOIN public.treated_clutches tc
    ON tc.clutch_instance_id = b.clutch_id
   AND tc.treated_clutch_code = b.baseline_code
  WHERE tc.id IS NULL
)
INSERT INTO public.treated_clutches (clutch_instance_id, treated_clutch_code, created_by, created_at)
SELECT clutch_id, baseline_code, 'system-baseline', clutch_created_at
FROM missing;

-- 3) Trigger to create the baseline group for every new clutch
CREATE OR REPLACE FUNCTION public.treated_clutches_ai_baseline()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO public.treated_clutches (clutch_instance_id, treated_clutch_code, created_by, created_at)
  VALUES (
    NEW.id,
    'T('||NEW.clutch_instance_code||')-0',
    COALESCE(current_setting('app.user', true), 'system'),
    COALESCE(NEW.created_at, now())
  )
  ON CONFLICT DO NOTHING;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_tc_ai_baseline ON public.clutch_instances;
CREATE TRIGGER trg_tc_ai_baseline
AFTER INSERT ON public.clutch_instances
FOR EACH ROW EXECUTE FUNCTION public.treated_clutches_ai_baseline();

COMMIT;

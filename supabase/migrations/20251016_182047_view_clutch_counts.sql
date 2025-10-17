BEGIN;

-- Fast helpers (idempotent)
CREATE INDEX IF NOT EXISTS ix_planned_crosses_clutch_id ON public.planned_crosses(clutch_id);
CREATE INDEX IF NOT EXISTS ix_planned_crosses_cross_id  ON public.planned_crosses(cross_id);
CREATE INDEX IF NOT EXISTS ix_cross_instances_cross_id  ON public.cross_instances(cross_id);
CREATE INDEX IF NOT EXISTS ix_clutch_instances_cross_instance_id ON public.clutch_instances(cross_instance_id);

CREATE OR REPLACE VIEW public.v_clutch_counts AS
WITH runs AS (
  SELECT
    cp.id                    AS clutch_id,
    cp.clutch_code,
    COUNT(DISTINCT ci.id)    AS runs_count,
    MAX(ci.cross_date)       AS last_run_date,
    MAX(ci.clutch_birthday)  AS last_birthday
  FROM public.clutch_plans cp
  LEFT JOIN public.planned_crosses pc ON pc.clutch_id = cp.id
  LEFT JOIN public.cross_instances ci ON ci.cross_id = pc.cross_id
  GROUP BY cp.id, cp.clutch_code
),
ann AS (
  SELECT
    cp.id                 AS clutch_id,
    COUNT(DISTINCT sel.id) AS annotations_count,
    MAX(sel.annotated_at)  AS last_annotated_at
  FROM public.clutch_plans cp
  LEFT JOIN public.planned_crosses pc ON pc.clutch_id = cp.id
  LEFT JOIN public.cross_instances ci ON ci.cross_id = pc.cross_id
  LEFT JOIN public.clutch_instances sel ON sel.cross_instance_id = ci.id
  GROUP BY cp.id
)
SELECT
  cp.clutch_code,
  COALESCE(r.runs_count, 0)         AS runs_count,
  COALESCE(a.annotations_count, 0)  AS annotations_count,
  r.last_run_date,
  r.last_birthday,
  a.last_annotated_at
FROM public.clutch_plans cp
LEFT JOIN runs r ON r.clutch_id = cp.id
LEFT JOIN ann  a ON a.clutch_id = cp.id;

COMMIT;

BEGIN;

CREATE TABLE IF NOT EXISTS public.fish_pairs (
  fish_pair_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mom_fish_code  text NOT NULL,
  dad_fish_code  text NOT NULL,
  genotype_elems text[] NULL,
  created_by     text NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  CHECK (mom_fish_code <> dad_fish_code)
);

CREATE INDEX IF NOT EXISTS idx_fish_pairs_mom ON public.fish_pairs(mom_fish_code);
CREATE INDEX IF NOT EXISTS idx_fish_pairs_dad ON public.fish_pairs(dad_fish_code);
CREATE INDEX IF NOT EXISTS idx_fish_pairs_created_at ON public.fish_pairs(created_at);

-- Summarized recent fish pairs (grouped mom/dad), enriched with last pair/run data if present
CREATE OR REPLACE VIEW public.v_fish_pairs_recent AS
WITH tp AS (
  SELECT
    vtm.fish_code AS mom,
    vtf.fish_code AS dad,
    tp.status,
    tp.created_at
  FROM public.tank_pairs tp
  LEFT JOIN public.v_tanks vtm ON vtm.tank_id = tp.mother_tank_id
  LEFT JOIN public.v_tanks vtf ON vtf.tank_id = tp.father_tank_id
),
agg_tp AS (
  SELECT
    mom, dad,
    count(*) FILTER (WHERE status='selected')::int  AS n_selected,
    count(*) FILTER (WHERE status='scheduled')::int AS n_scheduled,
    max(created_at) AS last_pair_at
  FROM tp
  WHERE mom IS NOT NULL AND dad IS NOT NULL
  GROUP BY mom, dad
),
last_run AS (
  SELECT DISTINCT ON (ci.tank_pair_id)
         ci.tank_pair_id, ci.created_at AS run_created_at
  FROM public.cross_instances ci
  ORDER BY ci.tank_pair_id, ci.created_at DESC NULLS LAST
),
pair_runs AS (
  SELECT vtm.fish_code AS mom, vtf.fish_code AS dad, lr.run_created_at
  FROM public.tank_pairs tp
  LEFT JOIN last_run lr        ON lr.tank_pair_id = tp.id
  LEFT JOIN public.v_tanks vtm ON vtm.tank_id     = tp.mother_tank_id
  LEFT JOIN public.v_tanks vtf ON vtf.tank_id     = tp.father_tank_id
),
agg_runs AS (
  SELECT mom, dad, max(run_created_at) AS last_run_at
  FROM pair_runs
  WHERE mom IS NOT NULL AND dad IS NOT NULL
  GROUP BY mom, dad
)
SELECT
  fp.mom_fish_code AS mom,
  fp.dad_fish_code AS dad,
  COALESCE(atp.n_selected,0)  AS n_selected,
  COALESCE(atp.n_scheduled,0) AS n_scheduled,
  atp.last_pair_at,
  ar.last_run_at,
  GREATEST(
    COALESCE(atp.last_pair_at, timestamp 'epoch'),
    COALESCE(ar.last_run_at,  timestamp 'epoch'),
    COALESCE(max(fp.created_at), timestamp 'epoch')
  ) AS last_activity_at
FROM public.fish_pairs fp
LEFT JOIN agg_tp   atp ON atp.mom = fp.mom_fish_code AND atp.dad = fp.dad_fish_code
LEFT JOIN agg_runs ar  ON ar.mom  = fp.mom_fish_code AND ar.dad  = fp.dad_fish_code
GROUP BY fp.mom_fish_code, fp.dad_fish_code, atp.n_selected, atp.n_scheduled, atp.last_pair_at, ar.last_run_at
ORDER BY last_activity_at DESC NULLS LAST;

COMMIT;

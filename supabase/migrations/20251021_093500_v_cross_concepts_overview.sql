BEGIN;

CREATE OR REPLACE VIEW public.v_cross_concepts_overview AS
WITH
cp AS (
  SELECT
    c.id::uuid                       AS clutch_id,
    c.clutch_code::text              AS clutch_code,
    c.planned_name::text             AS planned_name,
    c.planned_nickname::text         AS planned_nickname,
    c.mom_code::text                 AS mom_code,
    c.dad_code::text                 AS dad_code,
    COALESCE(c.status::text,'draft') AS status,
    c.created_at::timestamptz        AS created_at,
    COALESCE(c.created_by::text,'')  AS created_by
  FROM public.clutch_plans c
),
pc_counts AS (
  SELECT
    pc.clutch_id::uuid AS clutch_id,
    COUNT(*)::int       AS planned_count
  FROM public.planned_crosses pc
  GROUP BY pc.clutch_id
),
ci_rows AS (
  SELECT
    pc.clutch_id::uuid                AS clutch_id,
    ci.id::uuid                       AS cross_instance_id,
    ci.cross_run_code::text           AS cross_run_code,
    ci.cross_date::date               AS cross_date,
    COALESCE(ci.created_at, pc.created_at)::timestamptz AS ci_created_at
  FROM public.planned_crosses pc
  JOIN public.crosses x          ON x.id = pc.cross_id
  JOIN public.cross_instances ci ON ci.cross_id = x.id
),
ci_agg AS (
  SELECT
    clutch_id,
    COUNT(*)::int                      AS n_cross_instances,
    MAX(cross_date)::date              AS last_cross_date,
    (ARRAY_AGG(cross_instance_id ORDER BY ci_created_at DESC NULLS LAST))[1]::uuid AS last_ci_id
  FROM ci_rows
  GROUP BY clutch_id
),
last_clutch_instance AS (
  SELECT
    ca.clutch_id,
    (ARRAY_AGG(ci2.id ORDER BY ci2.created_at DESC NULLS LAST))[1]::uuid AS clutch_instance_id
  FROM ci_agg ca
  LEFT JOIN public.clutch_instances ci2
    ON ci2.cross_instance_id = ca.last_ci_id
  GROUP BY ca.clutch_id
),
mom_live AS (
  SELECT
    c.clutch_id,
    COUNT(*)::int AS mom_live_tanks_count
  FROM cp c
  JOIN public.fish fm              ON fm.fish_code = c.mom_code
  JOIN public.v_tanks_for_fish vt  ON vt.fish_id   = fm.id
  WHERE vt.status::text IN ('active','new_tank')
  GROUP BY c.clutch_id
),
dad_live AS (
  SELECT
    c.clutch_id,
    COUNT(*)::int AS dad_live_tanks_count
  FROM cp c
  JOIN public.fish fd              ON fd.fish_code = c.dad_code
  JOIN public.v_tanks_for_fish vt  ON vt.fish_id   = fd.id
  WHERE vt.status::text IN ('active','new_tank')
  GROUP BY c.clutch_id
),
mom_geno AS (
  SELECT v.fish_code, v.genotype_rollup::text AS mom_genotype
  FROM public.v_fish_overview_all v
),
dad_geno AS (
  SELECT v.fish_code, v.genotype_rollup::text AS dad_genotype
  FROM public.v_fish_overview_all v
)
SELECT
  c.clutch_code,
  c.planned_name,
  c.planned_nickname,
  c.mom_code,
  c.dad_code,
  COALESCE(mg.mom_genotype,'') AS mom_genotype,
  COALESCE(dg.dad_genotype,'') AS dad_genotype,
  COALESCE(c.planned_name, CONCAT_WS(' × ', mg.mom_genotype, dg.dad_genotype))::text AS cross_name,
  c.status,
  COALESCE(pct.planned_count, 0)                        AS planned_count,
  COALESCE(cia.n_cross_instances, 0)                    AS n_cross_instances,
  cia.last_cross_date                                   AS cross_date,
  (CASE WHEN cia.last_cross_date IS NOT NULL
        THEN (cia.last_cross_date + INTERVAL '1 day')::date
        ELSE NULL::date
   END)                                                 AS clutch_instance_birthday,
  lci.clutch_instance_id::text                          AS clutch_instance_id,
  c.created_at,
  c.created_by,
  (COALESCE(ml.mom_live_tanks_count,0) > 0
   AND COALESCE(dl.dad_live_tanks_count,0) > 0)         AS runnable,
  COALESCE(ml.mom_live_tanks_count,0)                   AS mom_live_tanks_count,
  COALESCE(dl.dad_live_tanks_count,0)                   AS dad_live_tanks_count
FROM cp c
LEFT JOIN pc_counts            pct ON pct.clutch_id = c.clutch_id
LEFT JOIN ci_agg               cia ON cia.clutch_id = c.clutch_id
LEFT JOIN last_clutch_instance lci ON lci.clutch_id = c.clutch_id
LEFT JOIN mom_live             ml  ON ml.clutch_id  = c.clutch_id
LEFT JOIN dad_live             dl  ON dl.clutch_id  = c.clutch_id
LEFT JOIN mom_geno             mg  ON mg.fish_code  = c.mom_code
LEFT JOIN dad_geno             dg  ON dg.fish_code  = c.dad_code
ORDER BY c.created_at DESC NULLS LAST;

COMMIT;

-- Final, ordered replace: drop dependent, then rebuild both views.

DROP VIEW IF EXISTS public.v_cross_clutch_instances;
DROP VIEW IF EXISTS public.v_fish_rich;

CREATE VIEW public.v_fish_rich AS
WITH tcounts AS (
  SELECT m.fish_uuid, COUNT(*)::int AS n_active_tanks
  FROM public.fish_tank_memberships m
  JOIN public.tanks t ON t.tank_uuid = m.tank_uuid
  WHERE t.status = 'active'
  GROUP BY m.fish_uuid
)
SELECT
  f.fish_uuid::uuid                     AS fish_uuid,
  f.fish_code::text                     AS fish_code,
  COALESCE(f.fish_name,'')::text        AS fish_name,
  COALESCE(f.fish_nickname,'')::text    AS fish_nickname,
  COALESCE(f.genetic_background,'')::text    AS genetic_background,
  COALESCE(f.line_building_stage,'')::text   AS line_building_stage,
  f.date_birth::date                    AS date_birth,
  COALESCE(a.allele_number,0)::int      AS allele_number,
  COALESCE(a.allele_code,'')::text      AS allele_code,
  COALESCE(tc.n_active_tanks,0)::int    AS n_active_tanks,
  COALESCE(g.transgene_pretty,'')::text AS transgene_pretty,
  COALESCE(g.genotype_rollup,'')::text  AS genotype_rollup,
  f.created_at::timestamptz             AS created_at
FROM public.fish f
LEFT JOIN tcounts tc                   ON tc.fish_uuid   = f.fish_uuid
LEFT JOIN public.v_transgene_alleles a ON a.fish_uuid    = f.fish_uuid   -- shim or real
LEFT JOIN public.v_fish_genotypes   g  ON g.fish_uuid    = f.fish_uuid;   -- shim or real

-- Recreate the dependent view with the expected contract (no data assumptions).
CREATE VIEW public.v_cross_clutch_instances AS
SELECT
  x.id::uuid                    AS cross_instance_id,
  x.cross_run_code::text        AS cross_code,
  x.tank_pair_code::text        AS tank_pair_code,
  tp.fish_pair_code::text       AS fish_pair_code,
  tp.mom_fish_code::text        AS mom_fish_code,
  tp.dad_fish_code::text        AS dad_fish_code,
  tp.mother_tank_code::text     AS mom_tank_code,
  tp.father_tank_code::text     AS dad_tank_code,
  fm.genotype_text::text        AS mom_genotype,
  fd.genotype_text::text        AS dad_genotype,
  NULL::text                    AS clutch_genotype,
  (x.cross_date)::date          AS cross_date,
  x.created_at::timestamptz     AS cross_created_at,
  ci.id::uuid                   AS clutch_instance_id,
  ci.clutch_instance_code::text AS clutch_code,
  ci.created_at::timestamptz    AS clutch_created_at
FROM public.cross_instances x
LEFT JOIN public.v_tank_pairs tp   ON tp.tank_pair_code = x.tank_pair_code
LEFT JOIN public.v_fish_rich fm    ON fm.fish_code      = tp.mom_fish_code
LEFT JOIN public.v_fish_rich fd    ON fd.fish_code      = tp.dad_fish_code
LEFT JOIN public.clutch_instances ci ON ci.cross_instance_id = x.id;

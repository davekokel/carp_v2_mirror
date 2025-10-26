-- Replace genotype stubs with real joins if v_fish_rich_derive_pretties exists
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'v'
      AND n.nspname = 'public'
      AND c.relname = 'v_fish_rich_derive_pretties'
  ) THEN
    EXECUTE $sql$
      DROP VIEW IF EXISTS public.v_cross_clutch_instances CASCADE;
      CREATE VIEW public.v_cross_clutch_instances AS
      SELECT
        ci.id                    AS cross_instance_id,
        ci.cross_run_code        AS cross_code,
        ci.tank_pair_code        AS tank_pair_code,
        tp.fish_pair_code        AS fish_pair_code,
        tp.mom_fish_code         AS mom_fish_code,
        tp.dad_fish_code         AS dad_fish_code,
        tp.mother_tank_code      AS mom_tank_code,
        tp.father_tank_code      AS dad_tank_code,
        pm.genotype_text         AS mom_genotype,
        pd.genotype_text         AS dad_genotype,
        CASE
          WHEN COALESCE(pm.genotype_text, '') <> '' AND COALESCE(pd.genotype_text, '') <> ''
            THEN pm.genotype_text || ' × ' || pd.genotype_text
          ELSE COALESCE(pm.genotype_text, pd.genotype_text)
        END AS clutch_genotype,
        ci.cross_date,
        ci.created_at            AS cross_created_at,
        cl.id                    AS clutch_instance_id,
        cl.clutch_instance_code  AS clutch_code,
        cl.created_at            AS clutch_created_at
      FROM public.cross_instances ci
      LEFT JOIN public.clutch_instances cl
        ON cl.cross_instance_id = ci.id
      LEFT JOIN public.v_tank_pairs tp
        ON tp.tank_pair_code = ci.tank_pair_code
      LEFT JOIN public.v_fish_rich_derive_pretties pm
        ON pm.fish_code = tp.mom_fish_code
      LEFT JOIN public.v_fish_rich_derive_pretties pd
        ON pd.fish_code = tp.dad_fish_code
      ORDER BY ci.created_at DESC NULLS LAST, ci.cross_date DESC NULLS LAST;

      DROP VIEW IF EXISTS public.v_clutches_overview CASCADE;
      CREATE VIEW public.v_clutches_overview AS
      WITH cp AS (
        SELECT
          c.id, c.clutch_code, c.planned_name, c.planned_nickname,
          c.mom_code, c.dad_code, c.created_at, c.created_by, c.note,
          NULL::text AS status
        FROM public.clutch_plans c
      ),
      parent AS (
        SELECT
          v.fish_code,
          vr.genotype_text,
          v.genetic_background,
          COALESCE(t.n_live, 0)::int AS live_tanks
        FROM public.v_fish v
        LEFT JOIN public.v_fish_rich_derive_pretties vr
          ON vr.fish_code = v.fish_code
        LEFT JOIN (
          SELECT vt.fish_code,
                 COUNT(*) FILTER (WHERE vt.status IN ('active','new_tank')) AS n_live
          FROM public.v_tanks vt
          GROUP BY vt.fish_code
        ) t USING (fish_code)
      ),
      pc AS (
        SELECT c.id AS clutch_plan_id, p.id AS planned_cross_id
        FROM public.clutch_plans c
        LEFT JOIN public.planned_crosses p ON p.clutch_id = c.id
      ),
      ci AS (
        SELECT pc.clutch_plan_id, ci2.id, ci2.cross_date, ci2.created_at
        FROM pc
        LEFT JOIN public.crosses x ON x.id = pc.planned_cross_id
        LEFT JOIN public.cross_instances ci2 ON ci2.cross_id = x.id
      ),
      ci_agg AS (
        SELECT ci.clutch_plan_id,
               COUNT(ci.id)::int AS cross_count,
               MAX(ci.cross_date) AS last_cross_date
        FROM ci
        GROUP BY ci.clutch_plan_id
      ),
      cl AS (
        SELECT pc.clutch_plan_id, cl2.clutch_instance_code,
               cl2.created_at, cl2.annotated_at
        FROM pc
        LEFT JOIN public.crosses x ON x.id = pc.planned_cross_id
        LEFT JOIN public.cross_instances ci2 ON ci2.cross_id = x.id
        LEFT JOIN public.clutch_instances cl2 ON cl2.cross_instance_id = ci2.id
      ),
      cl_agg AS (
        SELECT cl.clutch_plan_id,
               COUNT(cl.clutch_instance_code)::int AS annotation_count,
               MAX(cl.annotated_at) AS last_annotated_at,
               (ARRAY_AGG(cl.clutch_instance_code ORDER BY cl.created_at DESC NULLS LAST))[1]
                 AS last_clutch_code
        FROM cl
        GROUP BY cl.clutch_plan_id
      ),
      pc_count AS (
        SELECT pc.clutch_plan_id, COUNT(pc.planned_cross_id)::int AS planned_count
        FROM pc
        GROUP BY pc.clutch_plan_id
      )
      SELECT
        cp.clutch_code,
        cp.planned_name,
        cp.planned_nickname,
        cp.mom_code,
        pm.genetic_background AS mom_background,
        pm.genotype_text      AS mom_genotype,
        pm.live_tanks         AS mom_live_tanks,
        cp.dad_code,
        pd.genetic_background AS dad_background,
        pd.genotype_text      AS dad_genotype,
        pd.live_tanks         AS dad_live_tanks,
        COALESCE(pm.live_tanks, 0) > 0 AND COALESCE(pd.live_tanks, 0) > 0 AS runnable,
        COALESCE(pc_count.planned_count, 0) AS planned_count,
        COALESCE(ci_agg.cross_count, 0)     AS cross_count,
        ci_agg.last_cross_date,
        COALESCE(cl_agg.annotation_count, 0) AS annotation_count,
        cl_agg.last_annotated_at,
        cl_agg.last_clutch_code,
        cp.note,
        cp.status,
        cp.created_by,
        cp.created_at
      FROM cp
      LEFT JOIN parent pm ON pm.fish_code = cp.mom_code
      LEFT JOIN parent pd ON pd.fish_code = cp.dad_code
      LEFT JOIN pc_count  ON pc_count.clutch_plan_id = cp.id
      LEFT JOIN ci_agg    ON ci_agg.clutch_plan_id   = cp.id
      LEFT JOIN cl_agg    ON cl_agg.clutch_plan_id   = cp.id
      ORDER BY cp.created_at DESC NULLS LAST, cp.clutch_code;
    $sql$;
  ELSE
    RAISE NOTICE 'Skipping genotype join replacement because v_fish_rich_derive_pretties not yet created.';
  END IF;
END$$;
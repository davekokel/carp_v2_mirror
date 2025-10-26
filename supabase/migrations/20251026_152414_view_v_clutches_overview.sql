begin;
create or replace view public.v_clutches_overview as  WITH cp AS (
         SELECT c.id,
            c.clutch_code,
            c.planned_name,
            c.planned_nickname,
            c.mom_code,
            c.dad_code,
            c.created_at,
            c.created_by,
            c.note,
            NULL::text AS status
           FROM clutch_plans c
        ), parent AS (
         SELECT v.fish_code,
            NULL::text AS genotype_text,
            v.genetic_background,
            COALESCE(t.n_live, 0::bigint)::integer AS live_tanks
           FROM v_fish_rich v
             LEFT JOIN ( SELECT v_tanks.fish_code,
                    count(*) FILTER (WHERE v_tanks.status = ANY (ARRAY['active'::text, 'new_tank'::text])) AS n_live
                   FROM v_tanks
                  GROUP BY v_tanks.fish_code) t USING (fish_code)
        ), pc AS (
         SELECT c.id AS clutch_plan_id,
            p.id AS planned_cross_id
           FROM clutch_plans c
             LEFT JOIN planned_crosses p ON p.clutch_id = c.id
        ), ci AS (
         SELECT pc.clutch_plan_id,
            ci2.id,
            ci2.cross_date,
            ci2.created_at
           FROM pc
             LEFT JOIN crosses x ON x.id = pc.planned_cross_id
             LEFT JOIN cross_instances ci2 ON ci2.cross_id = x.id
        ), ci_agg AS (
         SELECT ci.clutch_plan_id,
            count(ci.id)::integer AS cross_count,
            max(ci.cross_date) AS last_cross_date
           FROM ci
          GROUP BY ci.clutch_plan_id
        ), cl AS (
         SELECT pc.clutch_plan_id,
            cl2.clutch_instance_code,
            cl2.created_at,
            cl2.annotated_at
           FROM pc
             LEFT JOIN crosses x ON x.id = pc.planned_cross_id
             LEFT JOIN cross_instances ci2 ON ci2.cross_id = x.id
             LEFT JOIN clutch_instances cl2 ON cl2.cross_instance_id = ci2.id
        ), cl_agg AS (
         SELECT cl.clutch_plan_id,
            count(cl.clutch_instance_code)::integer AS annotation_count,
            max(cl.annotated_at) AS last_annotated_at,
            (array_agg(cl.clutch_instance_code ORDER BY cl.created_at DESC NULLS LAST))[1] AS last_clutch_code
           FROM cl
          GROUP BY cl.clutch_plan_id
        ), pc_count AS (
         SELECT pc.clutch_plan_id,
            count(pc.planned_cross_id)::integer AS planned_count
           FROM pc
          GROUP BY pc.clutch_plan_id
        )
 SELECT cp.clutch_code,
    cp.planned_name,
    cp.planned_nickname,
    cp.mom_code,
    pm.genetic_background AS mom_background,
    pm.genotype_text AS mom_genotype,
    pm.live_tanks AS mom_live_tanks,
    cp.dad_code,
    pd.genetic_background AS dad_background,
    pd.genotype_text AS dad_genotype,
    pd.live_tanks AS dad_live_tanks,
    COALESCE(pm.live_tanks, 0) > 0 AND COALESCE(pd.live_tanks, 0) > 0 AS runnable,
    COALESCE(pc_count.planned_count, 0) AS planned_count,
    COALESCE(ci_agg.cross_count, 0) AS cross_count,
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
     LEFT JOIN pc_count ON pc_count.clutch_plan_id = cp.id
     LEFT JOIN ci_agg ON ci_agg.clutch_plan_id = cp.id
     LEFT JOIN cl_agg ON cl_agg.clutch_plan_id = cp.id
  ORDER BY cp.created_at DESC NULLS LAST, cp.clutch_code;;
commit;

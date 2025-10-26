begin;
create or replace view public.v_cross_clutch_instances (cross_instance_id, cross_code, tank_pair_code, fish_pair_code, mom_fish_code, dad_fish_code, mom_tank_code, dad_tank_code, mom_genotype, dad_genotype, clutch_genotype, cross_date, cross_created_at, clutch_instance_id, clutch_code, clutch_created_at) as  SELECT ci.id AS cross_instance_id,
    ci.cross_run_code AS cross_code,
    ci.tank_pair_code,
    tp.fish_pair_code,
    tp.mom_fish_code,
    tp.dad_fish_code,
    tp.mom_tank_code,
    tp.dad_tank_code,
    tp.mom_genotype,
    tp.dad_genotype,
        CASE
            WHEN COALESCE(tp.mom_genotype, ''::text) <> ''::text AND COALESCE(tp.dad_genotype, ''::text) <> ''::text THEN (tp.mom_genotype || ' × '::text) || tp.dad_genotype
            ELSE COALESCE(tp.mom_genotype, tp.dad_genotype)
        END AS clutch_genotype,
    ci.cross_date,
    ci.created_at AS cross_created_at,
    cl.id AS clutch_instance_id,
    cl.clutch_instance_code AS clutch_code,
    cl.created_at AS clutch_created_at
   FROM cross_instances ci
     LEFT JOIN clutch_instances cl ON cl.cross_instance_id = ci.id
     LEFT JOIN v_tank_pairs tp ON tp.tank_pair_code = ci.tank_pair_code
  ORDER BY ci.created_at DESC NULLS LAST, ci.cross_date DESC NULLS LAST;;
commit;

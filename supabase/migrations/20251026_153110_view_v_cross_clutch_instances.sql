begin;
create or replace view public.v_cross_clutch_instances as  SELECT ci.id AS cross_instance_id,
    ci.cross_run_code AS cross_code,
    ci.tank_pair_code,
    tp.fish_pair_code,
    tp.mom_fish_code,
    tp.dad_fish_code,
    ci.cross_date,
    ci.created_at AS cross_created_at,
    cl.id AS clutch_instance_id,
    cl.clutch_instance_code AS clutch_code,
    cl.created_at AS clutch_created_at
   FROM cross_instances ci
     LEFT JOIN clutch_instances cl ON cl.cross_instance_id = ci.id
     LEFT JOIN v_tank_pairs tp ON tp.tank_pair_code = ci.tank_pair_code;;
commit;

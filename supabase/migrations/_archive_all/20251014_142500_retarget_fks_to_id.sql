-- Drop FKs that reference parent(id_uuid) and recreate them to parent(id).

-- clutch_containers → clutches/containers
ALTER TABLE ONLY public.clutch_containers DROP CONSTRAINT IF EXISTS clutch_containers_clutch_id_fkey;
ALTER TABLE ONLY public.clutch_containers ADD  CONSTRAINT clutch_containers_clutch_id_fkey
  FOREIGN KEY (clutch_id) REFERENCES public.clutches(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.clutch_containers DROP CONSTRAINT IF EXISTS clutch_containers_container_id_fkey;
ALTER TABLE ONLY public.clutch_containers ADD  CONSTRAINT clutch_containers_container_id_fkey
  FOREIGN KEY (container_id) REFERENCES public.containers(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.clutch_containers DROP CONSTRAINT IF EXISTS clutch_containers_source_container_id_fkey;
ALTER TABLE ONLY public.clutch_containers ADD  CONSTRAINT clutch_containers_source_container_id_fkey
  FOREIGN KEY (source_container_id) REFERENCES public.containers(id) ON DELETE SET NULL;

-- clutch_genotype_options → clutches
ALTER TABLE ONLY public.clutch_genotype_options DROP CONSTRAINT IF EXISTS clutch_genotype_options_clutch_id_fkey;
ALTER TABLE ONLY public.clutch_genotype_options ADD  CONSTRAINT clutch_genotype_options_clutch_id_fkey
  FOREIGN KEY (clutch_id) REFERENCES public.clutches(id) ON DELETE CASCADE;

-- clutch_plan_treatments → clutch_plans
ALTER TABLE ONLY public.clutch_plan_treatments DROP CONSTRAINT IF EXISTS clutch_plan_treatments_clutch_id_fkey;
ALTER TABLE ONLY public.clutch_plan_treatments ADD  CONSTRAINT clutch_plan_treatments_clutch_id_fkey
  FOREIGN KEY (clutch_id) REFERENCES public.clutch_plans(id) ON DELETE CASCADE;

-- clutch_treatments → clutches
ALTER TABLE ONLY public.clutch_treatments DROP CONSTRAINT IF EXISTS clutch_treatments_clutch_id_fkey;
ALTER TABLE ONLY public.clutch_treatments ADD  CONSTRAINT clutch_treatments_clutch_id_fkey
  FOREIGN KEY (clutch_id) REFERENCES public.clutches(id) ON DELETE CASCADE;

-- clutches → crosses/cross_instances/planned_crosses
ALTER TABLE ONLY public.clutches DROP CONSTRAINT IF EXISTS clutches_cross_id_fkey;
ALTER TABLE ONLY public.clutches ADD  CONSTRAINT clutches_cross_id_fkey
  FOREIGN KEY (cross_id) REFERENCES public.crosses(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.clutches DROP CONSTRAINT IF EXISTS clutches_cross_instance_id_fkey;
ALTER TABLE ONLY public.clutches ADD  CONSTRAINT clutches_cross_instance_id_fkey
  FOREIGN KEY (cross_instance_id) REFERENCES public.cross_instances(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.clutches DROP CONSTRAINT IF EXISTS clutches_planned_cross_id_fkey;
ALTER TABLE ONLY public.clutches ADD  CONSTRAINT clutches_planned_cross_id_fkey
  FOREIGN KEY (planned_cross_id) REFERENCES public.planned_crosses(id);

-- container_status_history → containers
ALTER TABLE ONLY public.container_status_history DROP CONSTRAINT IF EXISTS container_status_history_container_id_fkey;
ALTER TABLE ONLY public.container_status_history ADD  CONSTRAINT container_status_history_container_id_fkey
  FOREIGN KEY (container_id) REFERENCES public.containers(id) ON DELETE CASCADE;

-- containers → tank_requests
ALTER TABLE ONLY public.containers DROP CONSTRAINT IF EXISTS containers_request_id_fkey;
ALTER TABLE ONLY public.containers ADD  CONSTRAINT containers_request_id_fkey
  FOREIGN KEY (request_id) REFERENCES public.tank_requests(id) ON DELETE SET NULL;

-- cross_instances → crosses/containers
ALTER TABLE ONLY public.cross_instances DROP CONSTRAINT IF EXISTS cross_instances_cross_id_fkey;
ALTER TABLE ONLY public.cross_instances ADD  CONSTRAINT cross_instances_cross_id_fkey
  FOREIGN KEY (cross_id) REFERENCES public.crosses(id);

ALTER TABLE ONLY public.cross_instances DROP CONSTRAINT IF EXISTS cross_instances_father_tank_id_fkey;
ALTER TABLE ONLY public.cross_instances ADD  CONSTRAINT cross_instances_father_tank_id_fkey
  FOREIGN KEY (father_tank_id) REFERENCES public.containers(id);

ALTER TABLE ONLY public.cross_instances DROP CONSTRAINT IF EXISTS cross_instances_mother_tank_id_fkey;
ALTER TABLE ONLY public.cross_instances ADD  CONSTRAINT cross_instances_mother_tank_id_fkey
  FOREIGN KEY (mother_tank_id) REFERENCES public.containers(id);

-- explicit aliases (same targets)
ALTER TABLE ONLY public.cross_instances DROP CONSTRAINT IF EXISTS fk_ci_cross;
ALTER TABLE ONLY public.cross_instances ADD  CONSTRAINT fk_ci_cross
  FOREIGN KEY (cross_id) REFERENCES public.crosses(id);

ALTER TABLE ONLY public.cross_instances DROP CONSTRAINT IF EXISTS fk_ci_father_container;
ALTER TABLE ONLY public.cross_instances ADD  CONSTRAINT fk_ci_father_container
  FOREIGN KEY (father_tank_id) REFERENCES public.containers(id);

ALTER TABLE ONLY public.cross_instances DROP CONSTRAINT IF EXISTS fk_ci_mother_container;
ALTER TABLE ONLY public.cross_instances ADD  CONSTRAINT fk_ci_mother_container
  FOREIGN KEY (mother_tank_id) REFERENCES public.containers(id);

-- cross_plan_runs → containers
ALTER TABLE ONLY public.cross_plan_runs DROP CONSTRAINT IF EXISTS cross_plan_runs_tank_a_id_fkey;
ALTER TABLE ONLY public.cross_plan_runs ADD  CONSTRAINT cross_plan_runs_tank_a_id_fkey
  FOREIGN KEY (tank_a_id) REFERENCES public.containers(id);

ALTER TABLE ONLY public.cross_plan_runs DROP CONSTRAINT IF EXISTS cross_plan_runs_tank_b_id_fkey;
ALTER TABLE ONLY public.cross_plan_runs ADD  CONSTRAINT cross_plan_runs_tank_b_id_fkey
  FOREIGN KEY (tank_b_id) REFERENCES public.containers(id);

-- cross_plans → containers
ALTER TABLE ONLY public.cross_plans DROP CONSTRAINT IF EXISTS fk_cross_plans_tank_a_cont;
ALTER TABLE ONLY public.cross_plans ADD  CONSTRAINT fk_cross_plans_tank_a_cont
  FOREIGN KEY (tank_a_id) REFERENCES public.containers(id);

ALTER TABLE ONLY public.cross_plans DROP CONSTRAINT IF EXISTS fk_cross_plans_tank_b_cont;
ALTER TABLE ONLY public.cross_plans ADD  CONSTRAINT fk_cross_plans_tank_b_cont
  FOREIGN KEY (tank_b_id) REFERENCES public.containers(id);

-- fish_tank_memberships → containers
ALTER TABLE ONLY public.fish_tank_memberships DROP CONSTRAINT IF EXISTS fish_tank_memberships_container_id_fkey;
ALTER TABLE ONLY public.fish_tank_memberships ADD  CONSTRAINT fish_tank_memberships_container_id_fkey
  FOREIGN KEY (container_id) REFERENCES public.containers(id) ON DELETE RESTRICT;

-- clutch_instances → cross_instances
ALTER TABLE ONLY public.clutch_instances DROP CONSTRAINT IF EXISTS fk_ci_xrun;
ALTER TABLE ONLY public.clutch_instances ADD  CONSTRAINT fk_ci_xrun
  FOREIGN KEY (cross_instance_id) REFERENCES public.cross_instances(id);

-- label_items → label_jobs/tank_requests/containers
ALTER TABLE ONLY public.label_items DROP CONSTRAINT IF EXISTS label_items_job_id_fkey;
ALTER TABLE ONLY public.label_items ADD  CONSTRAINT label_items_job_id_fkey
  FOREIGN KEY (job_id) REFERENCES public.label_jobs(id);

ALTER TABLE ONLY public.label_items DROP CONSTRAINT IF EXISTS label_items_request_id_fkey;
ALTER TABLE ONLY public.label_items ADD  CONSTRAINT label_items_request_id_fkey
  FOREIGN KEY (request_id) REFERENCES public.tank_requests(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.label_items DROP CONSTRAINT IF EXISTS label_items_tank_id_fkey;
ALTER TABLE ONLY public.label_items ADD  CONSTRAINT label_items_tank_id_fkey
  FOREIGN KEY (tank_id) REFERENCES public.containers(id) ON DELETE SET NULL;

-- planned_crosses → clutch_plans/crosses/cross_instances/containers
ALTER TABLE ONLY public.planned_crosses DROP CONSTRAINT IF EXISTS planned_crosses_clutch_id_fkey;
ALTER TABLE ONLY public.planned_crosses ADD  CONSTRAINT planned_crosses_clutch_id_fkey
  FOREIGN KEY (clutch_id) REFERENCES public.clutch_plans(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.planned_crosses DROP CONSTRAINT IF EXISTS planned_crosses_cross_id_fkey;
ALTER TABLE ONLY public.planned_crosses ADD  CONSTRAINT planned_crosses_cross_id_fkey
  FOREIGN KEY (cross_id) REFERENCES public.crosses(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.planned_crosses DROP CONSTRAINT IF EXISTS planned_crosses_cross_instance_id_fkey;
ALTER TABLE ONLY public.planned_crosses ADD  CONSTRAINT planned_crosses_cross_instance_id_fkey
  FOREIGN KEY (cross_instance_id) REFERENCES public.cross_instances(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.planned_crosses DROP CONSTRAINT IF EXISTS planned_crosses_father_tank_id_fkey;
ALTER TABLE ONLY public.planned_crosses ADD  CONSTRAINT planned_crosses_father_tank_id_fkey
  FOREIGN KEY (father_tank_id) REFERENCES public.containers(id);

ALTER TABLE ONLY public.planned_crosses DROP CONSTRAINT IF EXISTS planned_crosses_mother_tank_id_fkey;
ALTER TABLE ONLY public.planned_crosses ADD  CONSTRAINT planned_crosses_mother_tank_id_fkey
  FOREIGN KEY (mother_tank_id) REFERENCES public.containers(id);

-- rnas → plasmids
ALTER TABLE ONLY public.rnas DROP CONSTRAINT IF EXISTS rnas_source_plasmid_id_fkey;
ALTER TABLE ONLY public.rnas ADD  CONSTRAINT rnas_source_plasmid_id_fkey
  FOREIGN KEY (source_plasmid_id) REFERENCES public.plasmids(id) ON DELETE SET NULL;

-- tank_requests → fish
ALTER TABLE ONLY public.tank_requests DROP CONSTRAINT IF EXISTS tank_requests_fish_id_fkey;
ALTER TABLE ONLY public.tank_requests ADD  CONSTRAINT tank_requests_fish_id_fkey
  FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;

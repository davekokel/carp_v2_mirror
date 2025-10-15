-- 1) Drop all child FKs that reference containers(id_uuid)
ALTER TABLE ONLY public.clutch_containers              DROP CONSTRAINT IF EXISTS clutch_containers_container_id_fkey;
ALTER TABLE ONLY public.clutch_containers              DROP CONSTRAINT IF EXISTS clutch_containers_source_container_id_fkey;
ALTER TABLE ONLY public.container_status_history       DROP CONSTRAINT IF EXISTS container_status_history_container_id_fkey;
ALTER TABLE ONLY public.cross_instances                DROP CONSTRAINT IF EXISTS cross_instances_father_tank_id_fkey;
ALTER TABLE ONLY public.cross_instances                DROP CONSTRAINT IF EXISTS cross_instances_mother_tank_id_fkey;
ALTER TABLE ONLY public.cross_plan_runs                DROP CONSTRAINT IF EXISTS cross_plan_runs_tank_a_id_fkey;
ALTER TABLE ONLY public.cross_plan_runs                DROP CONSTRAINT IF EXISTS cross_plan_runs_tank_b_id_fkey;
ALTER TABLE ONLY public.fish_tank_memberships          DROP CONSTRAINT IF EXISTS fish_tank_memberships_container_id_fkey;
ALTER TABLE ONLY public.cross_instances                DROP CONSTRAINT IF EXISTS fk_ci_father_container;
ALTER TABLE ONLY public.cross_instances                DROP CONSTRAINT IF EXISTS fk_ci_mother_container;
ALTER TABLE ONLY public.cross_plans                    DROP CONSTRAINT IF EXISTS fk_cross_plans_tank_a_cont;
ALTER TABLE ONLY public.cross_plans                    DROP CONSTRAINT IF EXISTS fk_cross_plans_tank_b_cont;
ALTER TABLE ONLY public.label_items                    DROP CONSTRAINT IF EXISTS label_items_tank_id_fkey;
ALTER TABLE ONLY public.planned_crosses                DROP CONSTRAINT IF EXISTS planned_crosses_father_tank_id_fkey;
ALTER TABLE ONLY public.planned_crosses                DROP CONSTRAINT IF EXISTS planned_crosses_mother_tank_id_fkey;

-- 2) Ensure containers.id exists and flip PK to (id)
ALTER TABLE public.containers ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.containers SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.containers ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.containers ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO 28762
BEGIN
DECLARE pk text;
BEGIN
  SELECT c.conname INTO pk
  FROM pg_constraint c
  JOIN pg_class cl ON cl.oid=c.conrelid
  JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='containers';
  IF pk IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.containers DROP CONSTRAINT '||quote_ident(pk);
  END IF;
  EXECUTE 'ALTER TABLE public.containers ADD CONSTRAINT containers_pkey PRIMARY KEY (id)';
END;
END;
$$ LANGUAGE plpgsql;

-- clean transition bits and drop id_uuid now that no views/FKs depend on it
ALTER TABLE public.containers DROP CONSTRAINT IF EXISTS containers_id_equals_id_uuid;
DROP INDEX IF EXISTS public.containers_id_key;
ALTER TABLE public.containers DROP COLUMN IF EXISTS id_uuid;

-- 3) Recreate child FKs to containers(id)
ALTER TABLE ONLY public.clutch_containers
  ADD CONSTRAINT clutch_containers_container_id_fkey
  FOREIGN KEY (container_id) REFERENCES public.containers(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.clutch_containers
  ADD CONSTRAINT clutch_containers_source_container_id_fkey
  FOREIGN KEY (source_container_id) REFERENCES public.containers(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.container_status_history
  ADD CONSTRAINT container_status_history_container_id_fkey
  FOREIGN KEY (container_id) REFERENCES public.containers(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.cross_instances
  ADD CONSTRAINT cross_instances_father_tank_id_fkey
  FOREIGN KEY (father_tank_id) REFERENCES public.containers(id);

ALTER TABLE ONLY public.cross_instances
  ADD CONSTRAINT cross_instances_mother_tank_id_fkey
  FOREIGN KEY (mother_tank_id) REFERENCES public.containers(id);

ALTER TABLE ONLY public.cross_plan_runs
  ADD CONSTRAINT cross_plan_runs_tank_a_id_fkey
  FOREIGN KEY (tank_a_id) REFERENCES public.containers(id);

ALTER TABLE ONLY public.cross_plan_runs
  ADD CONSTRAINT cross_plan_runs_tank_b_id_fkey
  FOREIGN KEY (tank_b_id) REFERENCES public.containers(id);

ALTER TABLE ONLY public.fish_tank_memberships
  ADD CONSTRAINT fish_tank_memberships_container_id_fkey
  FOREIGN KEY (container_id) REFERENCES public.containers(id);

ALTER TABLE ONLY public.cross_instances
  ADD CONSTRAINT fk_ci_father_container
  FOREIGN KEY (father_tank_id) REFERENCES public.containers(id);

ALTER TABLE ONLY public.cross_instances
  ADD CONSTRAINT fk_ci_mother_container
  FOREIGN KEY (mother_tank_id) REFERENCES public.containers(id);

ALTER TABLE ONLY public.cross_plans
  ADD CONSTRAINT fk_cross_plans_tank_a_cont
  FOREIGN KEY (tank_a_id) REFERENCES public.containers(id);

ALTER TABLE ONLY public.cross_plans
  ADD CONSTRAINT fk_cross_plans_tank_b_cont
  FOREIGN KEY (tank_b_id) REFERENCES public.containers(id);

ALTER TABLE ONLY public.label_items
  ADD CONSTRAINT label_items_tank_id_fkey
  FOREIGN KEY (tank_id) REFERENCES public.containers(id);

ALTER TABLE ONLY public.planned_crosses
  ADD CONSTRAINT planned_crosses_father_tank_id_fkey
  FOREIGN KEY (father_tank_id) REFERENCES public.containers(id);

ALTER TABLE ONLY public.planned_crosses
  ADD CONSTRAINT planned_crosses_mother_tank_id_fkey
  FOREIGN KEY (mother_tank_id) REFERENCES public.containers(id);

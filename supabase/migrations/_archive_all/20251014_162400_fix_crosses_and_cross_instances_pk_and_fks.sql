-- Drop child FKs that reference crosses.id_uuid
ALTER TABLE ONLY public.clutches DROP CONSTRAINT IF EXISTS clutches_cross_id_fkey;
ALTER TABLE ONLY public.cross_instances DROP CONSTRAINT IF EXISTS cross_instances_cross_id_fkey;
ALTER TABLE ONLY public.cross_instances DROP CONSTRAINT IF EXISTS fk_ci_cross;
ALTER TABLE ONLY public.planned_crosses DROP CONSTRAINT IF EXISTS planned_crosses_cross_id_fkey;

-- Drop child FKs that reference cross_instances.id_uuid
ALTER TABLE ONLY public.clutches DROP CONSTRAINT IF EXISTS clutches_cross_instance_id_fkey;
ALTER TABLE ONLY public.planned_crosses DROP CONSTRAINT IF EXISTS planned_crosses_cross_instance_id_fkey;
ALTER TABLE ONLY public.clutch_instances DROP CONSTRAINT IF EXISTS fk_ci_xrun;

-- crosses: ensure id, swap PK, drop id_uuid
ALTER TABLE public.crosses ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.crosses SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.crosses ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.crosses ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO $$
BEGIN
DECLARE pk text;
BEGIN
  SELECT c.conname INTO pk
  FROM pg_constraint c
  JOIN pg_class cl ON cl.oid=c.conrelid
  JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='crosses';
  IF pk IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.crosses DROP CONSTRAINT '||quote_ident(pk);
  END IF;
  EXECUTE 'ALTER TABLE public.crosses ADD CONSTRAINT crosses_pkey PRIMARY KEY (id)';
END;
END;
$$ LANGUAGE plpgsql;
ALTER TABLE public.crosses DROP CONSTRAINT IF EXISTS crosses_id_equals_id_uuid;
DROP INDEX IF EXISTS public.crosses_id_key;
ALTER TABLE public.crosses DROP COLUMN IF EXISTS id_uuid;

-- cross_instances: ensure id, swap PK, drop id_uuid
ALTER TABLE public.cross_instances ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.cross_instances SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.cross_instances ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.cross_instances ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO $$
BEGIN
DECLARE pk text;
BEGIN
  SELECT c.conname INTO pk
  FROM pg_constraint c
  JOIN pg_class cl ON cl.oid=c.conrelid
  JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='cross_instances';
  IF pk IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.cross_instances DROP CONSTRAINT '||quote_ident(pk);
  END IF;
  EXECUTE 'ALTER TABLE public.cross_instances ADD CONSTRAINT cross_instances_pkey PRIMARY KEY (id)';
END;
END;
$$ LANGUAGE plpgsql;
ALTER TABLE public.cross_instances DROP CONSTRAINT IF EXISTS cross_instances_id_equals_id_uuid;
DROP INDEX IF EXISTS public.cross_instances_id_key;
ALTER TABLE public.cross_instances DROP COLUMN IF EXISTS id_uuid;

-- Recreate child FKs to crosses(id)
ALTER TABLE ONLY public.clutches
  ADD CONSTRAINT clutches_cross_id_fkey
  FOREIGN KEY (cross_id) REFERENCES public.crosses(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.cross_instances
  ADD CONSTRAINT cross_instances_cross_id_fkey
  FOREIGN KEY (cross_id) REFERENCES public.crosses(id);
ALTER TABLE ONLY public.cross_instances
  ADD CONSTRAINT fk_ci_cross
  FOREIGN KEY (cross_id) REFERENCES public.crosses(id);
ALTER TABLE ONLY public.planned_crosses
  ADD CONSTRAINT planned_crosses_cross_id_fkey
  FOREIGN KEY (cross_id) REFERENCES public.crosses(id);

-- Recreate child FKs to cross_instances(id)
ALTER TABLE ONLY public.clutches
  ADD CONSTRAINT clutches_cross_instance_id_fkey
  FOREIGN KEY (cross_instance_id) REFERENCES public.cross_instances(id);
ALTER TABLE ONLY public.planned_crosses
  ADD CONSTRAINT planned_crosses_cross_instance_id_fkey
  FOREIGN KEY (cross_instance_id) REFERENCES public.cross_instances(id);
ALTER TABLE ONLY public.clutch_instances
  ADD CONSTRAINT fk_ci_xrun
  FOREIGN KEY (cross_instance_id) REFERENCES public.cross_instances(id);

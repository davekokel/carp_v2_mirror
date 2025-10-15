-- 1) Drop child FKs that still reference parent(id_uuid)
ALTER TABLE ONLY public.containers DROP CONSTRAINT IF EXISTS containers_request_id_fkey;
ALTER TABLE ONLY public.label_items DROP CONSTRAINT IF EXISTS label_items_request_id_fkey;
ALTER TABLE ONLY public.label_items DROP CONSTRAINT IF EXISTS label_items_job_id_fkey;
ALTER TABLE ONLY public.rnas DROP CONSTRAINT IF EXISTS rnas_source_plasmid_id_fkey;
ALTER TABLE ONLY public.fish_seed_batches_map DROP CONSTRAINT IF EXISTS fk_fsbm_fish;
ALTER TABLE ONLY public.tank_requests DROP CONSTRAINT IF EXISTS tank_requests_fish_id_fkey;

-- 2) Ensure parents expose id and have PK(id), then drop id_uuid if present

-- tank_requests
DO $$
BEGIN
DECLARE pk text;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='tank_requests' AND column_name='id') THEN
    EXECUTE 'ALTER TABLE public.tank_requests ADD COLUMN id uuid';
    EXECUTE 'UPDATE public.tank_requests SET id = id_uuid WHERE id IS NULL';
    EXECUTE 'ALTER TABLE public.tank_requests ALTER COLUMN id SET NOT NULL';
    EXECUTE 'ALTER TABLE public.tank_requests ALTER COLUMN id SET DEFAULT gen_random_uuid()';
  END IF;
  SELECT c.conname INTO pk
  FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid
  JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='tank_requests';
  IF pk IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.tank_requests DROP CONSTRAINT '||quote_ident(pk);
  END IF;
  EXECUTE 'ALTER TABLE public.tank_requests ADD CONSTRAINT tank_requests_pkey PRIMARY KEY (id)';
END;
END;
$$ LANGUAGE plpgsql;
ALTER TABLE public.tank_requests DROP CONSTRAINT IF EXISTS tank_requests_id_equals_id_uuid;
DROP INDEX IF EXISTS public.tank_requests_id_key;
ALTER TABLE public.tank_requests DROP COLUMN IF EXISTS id_uuid;

-- label_jobs
DO $$
BEGIN
DECLARE pk text;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='label_jobs' AND column_name='id') THEN
    EXECUTE 'ALTER TABLE public.label_jobs ADD COLUMN id uuid';
    EXECUTE 'UPDATE public.label_jobs SET id = id_uuid WHERE id IS NULL';
    EXECUTE 'ALTER TABLE public.label_jobs ALTER COLUMN id SET NOT NULL';
    EXECUTE 'ALTER TABLE public.label_jobs ALTER COLUMN id SET DEFAULT gen_random_uuid()';
  END IF;
  SELECT c.conname INTO pk
  FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid
  JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='label_jobs';
  IF pk IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.label_jobs DROP CONSTRAINT '||quote_ident(pk);
  END IF;
  EXECUTE 'ALTER TABLE public.label_jobs ADD CONSTRAINT label_jobs_pkey PRIMARY KEY (id)';
END;
END;
$$ LANGUAGE plpgsql;
ALTER TABLE public.label_jobs DROP CONSTRAINT IF EXISTS label_jobs_id_equals_id_uuid;
DROP INDEX IF EXISTS public.label_jobs_id_key;
ALTER TABLE public.label_jobs DROP COLUMN IF EXISTS id_uuid;

-- plasmids
DO $$
BEGIN
DECLARE pk text;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='plasmids' AND column_name='id') THEN
    EXECUTE 'ALTER TABLE public.plasmids ADD COLUMN id uuid';
    EXECUTE 'UPDATE public.plasmids SET id = id_uuid WHERE id IS NULL';
    EXECUTE 'ALTER TABLE public.plasmids ALTER COLUMN id SET NOT NULL';
    EXECUTE 'ALTER TABLE public.plasmids ALTER COLUMN id SET DEFAULT gen_random_uuid()';
  END IF;
  SELECT c.conname INTO pk
  FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid
  JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='plasmids';
  IF pk IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.plasmids DROP CONSTRAINT '||quote_ident(pk);
  END IF;
  EXECUTE 'ALTER TABLE public.plasmids ADD CONSTRAINT plasmids_pkey PRIMARY KEY (id)';
END;
END;
$$ LANGUAGE plpgsql;
ALTER TABLE public.plasmids DROP CONSTRAINT IF EXISTS plasmids_id_equals_id_uuid;
DROP INDEX IF EXISTS public.plasmids_id_key;
ALTER TABLE public.plasmids DROP COLUMN IF EXISTS id_uuid;

-- fish
DO $$
BEGIN
DECLARE pk text;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='fish' AND column_name='id') THEN
    EXECUTE 'ALTER TABLE public.fish ADD COLUMN id uuid';
    EXECUTE 'UPDATE public.fish SET id = id_uuid WHERE id IS NULL';
    EXECUTE 'ALTER TABLE public.fish ALTER COLUMN id SET NOT NULL';
    EXECUTE 'ALTER TABLE public.fish ALTER COLUMN id SET DEFAULT gen_random_uuid()';
  END IF;
  SELECT c.conname INTO pk
  FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid
  JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='fish';
  IF pk IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.fish DROP CONSTRAINT '||quote_ident(pk);
  END IF;
  EXECUTE 'ALTER TABLE public.fish ADD CONSTRAINT fish_pkey PRIMARY KEY (id)';
END;
END;
$$ LANGUAGE plpgsql;
ALTER TABLE public.fish DROP CONSTRAINT IF EXISTS fish_id_equals_id_uuid;
DROP INDEX IF EXISTS public.fish_id_key;
ALTER TABLE public.fish DROP COLUMN IF EXISTS id_uuid;

-- 3) Recreate child FKs now targeting parent(id)

ALTER TABLE ONLY public.containers
  ADD CONSTRAINT containers_request_id_fkey
  FOREIGN KEY (request_id) REFERENCES public.tank_requests(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.label_items
  ADD CONSTRAINT label_items_request_id_fkey
  FOREIGN KEY (request_id) REFERENCES public.tank_requests(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.label_items
  ADD CONSTRAINT label_items_job_id_fkey
  FOREIGN KEY (job_id) REFERENCES public.label_jobs(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.rnas
  ADD CONSTRAINT rnas_source_plasmid_id_fkey
  FOREIGN KEY (source_plasmid_id) REFERENCES public.plasmids(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.fish_seed_batches_map
  ADD CONSTRAINT fk_fsbm_fish
  FOREIGN KEY (fish_id) REFERENCES public.fish(id) DEFERRABLE INITIALLY DEFERRED ON DELETE CASCADE;

ALTER TABLE ONLY public.tank_requests
  ADD CONSTRAINT tank_requests_fish_id_fkey
  FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;

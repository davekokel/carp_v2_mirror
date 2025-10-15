-- Ensure fish.id exists, is filled, and has a default
ALTER TABLE public.fish ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.fish SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.fish ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.fish ALTER COLUMN id SET DEFAULT gen_random_uuid();

-- Drop FKs that still reference fish(id_uuid)
ALTER TABLE ONLY public.fish_seed_batches DROP CONSTRAINT IF EXISTS fk_fsbm_fish;
ALTER TABLE ONLY public.tank_requests     DROP CONSTRAINT IF EXISTS tank_requests_fish_id_fkey;

-- Swap fish PK to (id);
DO 28762
BEGIN
DECLARE pkname text;
BEGIN
  SELECT c.conname INTO pkname
  FROM pg_constraint c
  JOIN pg_class cl ON cl.oid=c.conrelid
  JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='fish';
  IF pkname IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.fish DROP CONSTRAINT '||quote_ident(pkname);
  END IF;
  EXECUTE 'ALTER TABLE public.fish ADD CONSTRAINT fish_pkey PRIMARY KEY (id)';
END;
END;
$$ LANGUAGE plpgsql;

-- Drop transitional CHECK/index; then drop id_uuid
ALTER TABLE public.fish DROP CONSTRAINT IF EXISTS fish_id_equals_id_uuid;
DROP INDEX IF EXISTS public.fish_id_key;
ALTER TABLE public.fish DROP COLUMN IF EXISTS id_uuid;

-- Recreate FKs pointing at fish(id)
ALTER TABLE ONLY public.fish_seed_batches
  ADD CONSTRAINT fk_fsbm_fish
  FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE ONLY public.tank_requests
  ADD CONSTRAINT tank_requests_fish_id_fkey
  FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;

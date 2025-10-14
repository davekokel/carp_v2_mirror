-- Fix clutches PK swap and dependent child FKs
ALTER TABLE ONLY public.clutch_genotype_options DROP CONSTRAINT IF EXISTS clutch_genotype_options_clutch_id_fkey;
ALTER TABLE ONLY public.clutch_treatments DROP CONSTRAINT IF EXISTS clutch_treatments_clutch_id_fkey;

ALTER TABLE public.clutches ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.clutches SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.clutches ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.clutches ALTER COLUMN id SET DEFAULT gen_random_uuid();

DO $$
DECLARE pk text;
BEGIN
  SELECT c.conname INTO pk
  FROM pg_constraint c
  JOIN pg_class cl ON cl.oid=c.conrelid
  JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='clutches';
  IF pk IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.clutches DROP CONSTRAINT '||quote_ident(pk);
  END IF;
  EXECUTE 'ALTER TABLE public.clutches ADD CONSTRAINT clutches_pkey PRIMARY KEY (id)';
END $$;

ALTER TABLE public.clutches DROP CONSTRAINT IF EXISTS clutches_id_equals_id_uuid;
DROP INDEX IF EXISTS public.clutches_id_key;
ALTER TABLE public.clutches DROP COLUMN IF EXISTS id_uuid;

-- Recreate child FKs
ALTER TABLE ONLY public.clutch_genotype_options
  ADD CONSTRAINT clutch_genotype_options_clutch_id_fkey
  FOREIGN KEY (clutch_id) REFERENCES public.clutches(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.clutch_treatments
  ADD CONSTRAINT clutch_treatments_clutch_id_fkey
  FOREIGN KEY (clutch_id) REFERENCES public.clutches(id) ON DELETE CASCADE;

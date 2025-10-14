-- Fix clutch_plans PK swap and dependent FKs
ALTER TABLE ONLY public.clutch_plan_treatments DROP CONSTRAINT IF EXISTS clutch_plan_treatments_clutch_id_fkey;
ALTER TABLE ONLY public.planned_crosses         DROP CONSTRAINT IF EXISTS planned_crosses_clutch_id_fkey;

ALTER TABLE public.clutch_plans ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.clutch_plans SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.clutch_plans ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.clutch_plans ALTER COLUMN id SET DEFAULT gen_random_uuid();

DO $$
DECLARE pk text;
BEGIN
  SELECT c.conname INTO pk
  FROM pg_constraint c
  JOIN pg_class cl ON cl.oid=c.conrelid
  JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='clutch_plans';
  IF pk IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.clutch_plans DROP CONSTRAINT '||quote_ident(pk);
  END IF;
  EXECUTE 'ALTER TABLE public.clutch_plans ADD CONSTRAINT clutch_plans_pkey PRIMARY KEY (id)';
END $$;

ALTER TABLE public.clutch_plans DROP CONSTRAINT IF EXISTS clutch_plans_id_equals_id_uuid;
DROP INDEX IF EXISTS public.clutch_plans_id_key;
ALTER TABLE public.clutch_plans DROP COLUMN IF EXISTS id_uuid;

ALTER TABLE ONLY public.clutch_plan_treatments
  ADD CONSTRAINT clutch_plan_treatments_clutch_id_fkey
  FOREIGN KEY (clutch_id) REFERENCES public.clutch_plans(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.planned_crosses
  ADD CONSTRAINT planned_crosses_clutch_id_fkey
  FOREIGN KEY (clutch_id) REFERENCES public.clutch_plans(id) ON DELETE CASCADE;

-- Add and migrate id on planned_crosses
ALTER TABLE public.planned_crosses ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.planned_crosses SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.planned_crosses ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.planned_crosses ALTER COLUMN id SET DEFAULT gen_random_uuid();

-- Drop existing PK (if any) and add new one on id
DO $$
BEGIN
DECLARE pk text;
BEGIN
  SELECT c.conname INTO pk
  FROM pg_constraint c
  JOIN pg_class cl ON cl.oid=c.conrelid
  JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='planned_crosses';
  IF pk IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.planned_crosses DROP CONSTRAINT '||quote_ident(pk);
  END IF;
  EXECUTE 'ALTER TABLE public.planned_crosses ADD CONSTRAINT planned_crosses_pkey PRIMARY KEY (id)';
END;
END;
$$ LANGUAGE plpgsql;

ALTER TABLE public.planned_crosses DROP CONSTRAINT IF EXISTS planned_crosses_id_equals_id_uuid;
DROP INDEX IF EXISTS public.planned_crosses_id_key;
ALTER TABLE public.planned_crosses DROP COLUMN IF EXISTS id_uuid;

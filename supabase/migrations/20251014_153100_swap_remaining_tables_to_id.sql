-- Final wave: swap PKs from id_uuid → id for remaining core tables
DO $$
DECLARE t text; pk text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'clutches',
    'containers',
    'cross_instances',
    'crosses',
    'label_items',
    'label_jobs',
    'plasmids',
    'rnas',
    'selection_labels',
    'tank_requests'
  ]
  LOOP
    -- Ensure id column exists
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name=t AND column_name='id'
    ) THEN
      EXECUTE format('ALTER TABLE public.%I ADD COLUMN id uuid', t);
      EXECUTE format('UPDATE public.%I SET id = id_uuid WHERE id IS NULL', t);
      EXECUTE format('ALTER TABLE public.%I ALTER COLUMN id SET DEFAULT gen_random_uuid()', t);
    END IF;

    -- Replace PK
    SELECT c.conname INTO pk
    FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid
    JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
    WHERE c.contype='p' AND cl.relname=t;
    IF pk IS NOT NULL THEN
      EXECUTE format('ALTER TABLE public.%I DROP CONSTRAINT %I', t, pk);
    END IF;
    EXECUTE format('ALTER TABLE public.%I ADD CONSTRAINT %I PRIMARY KEY (id)', t, t||'_pkey');

    -- Clean transition bits
    EXECUTE format('ALTER TABLE public.%I DROP CONSTRAINT IF EXISTS %I', t, t||'_id_equals_id_uuid');
    EXECUTE format('DROP INDEX IF EXISTS public.%I', t||'_id_key');
    EXECUTE format('ALTER TABLE public.%I DROP COLUMN IF EXISTS id_uuid', t);
  END LOOP;
END $$;

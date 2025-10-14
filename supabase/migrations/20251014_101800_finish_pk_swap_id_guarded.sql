DO $$
DECLARE
  t text;
  pkname text;
  has_iduuid boolean;
  pk_on_id  boolean;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'clutch_genotype_options',
    'clutch_plan_treatments',
    'clutch_plans',
    'clutch_treatments',
    'clutches',
    'containers',
    'cross_instances',
    'crosses',
    'label_items',
    'planned_crosses',
    'plasmids',
    'rnas',
    'selection_labels',
    'tank_requests'
  ]
  LOOP
    -- Ensure id exists and is NOT NULL with default
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name=t AND column_name='id'
    ) THEN
      EXECUTE format('ALTER TABLE public.%I ADD COLUMN id uuid', t);
    END IF;
    EXECUTE format('ALTER TABLE public.%I ALTER COLUMN id SET NOT NULL', t);
    EXECUTE format('ALTER TABLE public.%I ALTER COLUMN id SET DEFAULT gen_random_uuid()', t);

    -- Backfill id from id_uuid if that column still exists
    SELECT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name=t AND column_name='id_uuid'
    ) INTO has_iduuid;

    IF has_iduuid THEN
      EXECUTE format('UPDATE public.%I SET id = id_uuid WHERE id IS NULL', t);
    END IF;

    -- Is the current PK already on (id)?
    SELECT EXISTS (
      SELECT 1
      FROM pg_constraint c
      JOIN pg_class cl ON cl.oid=c.conrelid
      JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
      JOIN LATERAL unnest(c.conkey) k(k) ON TRUE
      JOIN pg_attribute a ON a.attrelid=cl.oid AND a.attnum=k.k
      WHERE c.contype='p' AND cl.relname=t AND a.attname='id'
    ) INTO pk_on_id;

    IF NOT pk_on_id THEN
      -- Drop current PK (whatever its name) and add PK(id)
      SELECT c.conname
        INTO pkname
      FROM pg_constraint c
      JOIN pg_class cl ON cl.oid=c.conrelid
      JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
      WHERE c.contype='p' AND cl.relname=t;

      IF pkname IS NOT NULL THEN
        EXECUTE format('ALTER TABLE public.%I DROP CONSTRAINT %I', t, pkname);
      END IF;

      EXECUTE format('ALTER TABLE public.%I ADD CONSTRAINT %I PRIMARY KEY (id)', t, t||'_pkey');
    END IF;

    -- Drop transitional CHECK/unique index if present (no-op if absent)
    EXECUTE format('ALTER TABLE public.%I DROP CONSTRAINT IF EXISTS %I', t, t||'_id_equals_id_uuid');
    EXECUTE format('DROP INDEX IF EXISTS public.%I', t||'_id_key');

    -- Drop id_uuid if still present
    IF has_iduuid THEN
      EXECUTE format('ALTER TABLE public.%I DROP COLUMN IF EXISTS id_uuid', t);
    END IF;
  END LOOP;
END $$;

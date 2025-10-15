-- Ensure id exists, is populated, and has sensible defaults, then swap PK(id_uuid) -> PK(id) and drop id_uuid.

DO $$
BEGIN
DECLARE t text;
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
    -- add/backfill id if missing
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=t AND column_name='id') THEN
      EXECUTE format('ALTER TABLE public.%I ADD COLUMN id uuid', t);
      EXECUTE format('UPDATE public.%I SET id = id_uuid WHERE id IS NULL', t);
    END IF;
    EXECUTE format('ALTER TABLE public.%I ALTER COLUMN id SET NOT NULL', t);
    EXECUTE format('ALTER TABLE public.%I ALTER COLUMN id SET DEFAULT gen_random_uuid()', t);

    -- swap primary key to (id) if currently on id_uuid
    PERFORM 1
    FROM pg_constraint c
    JOIN pg_class cl ON cl.oid=c.conrelid
    JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
    JOIN LATERAL unnest(c.conkey) k(k) ON TRUE
    JOIN pg_attribute a ON a.attrelid=cl.oid AND a.attnum=k.k
    WHERE c.contype='p' AND cl.relname=t AND a.attname='id';

    IF NOT FOUND THEN
      -- drop current PK and re-add on (id)
      EXECUTE format($f$ DO;
END;
$$ LANGUAGE plpgsql;DECLARE pkname text;
        BEGIN
          SELECT c.conname INTO pkname
          FROM pg_constraint c
          JOIN pg_class cl ON cl.oid=c.conrelid
          JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
          WHERE c.contype='p' AND cl.relname=%L;
          IF pkname IS NOT NULL THEN
            EXECUTE format('ALTER TABLE public.%I DROP CONSTRAINT %I', %L, pkname);
          END IF;
          EXECUTE format('ALTER TABLE public.%I ADD CONSTRAINT %I PRIMARY KEY (id)', %L, %L||'_pkey', %L);
        END $$; $f$, t, t, t, t, t);
    END IF;

    -- drop transitional check/index if present
    EXECUTE format('ALTER TABLE public.%I DROP CONSTRAINT IF EXISTS %I', t, t||'_id_equals_id_uuid');
    EXECUTE format('DROP INDEX IF EXISTS public.%I', t||'_id_key');

    -- drop id_uuid if present
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=t AND column_name='id_uuid') THEN
      EXECUTE format('ALTER TABLE public.%I DROP COLUMN id_uuid', t);
    END IF;
  END LOOP;
END $$;

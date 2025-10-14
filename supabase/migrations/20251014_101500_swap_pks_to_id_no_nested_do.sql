-- For each table: ensure id exists/backfilled, swap PK to (id), drop transition bits, drop id_uuid.

-- helpers: per-table block that (1) drops existing PK (whatever name) and (2) adds PRIMARY KEY(id)
-- we use one DO block per table (not nested), no dynamic DO inside EXECUTE.

-- clutch_genotype_options
ALTER TABLE public.clutch_genotype_options ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.clutch_genotype_options SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.clutch_genotype_options ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.clutch_genotype_options ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO $$
DECLARE pkname text;
BEGIN
  SELECT c.conname INTO pkname
  FROM pg_constraint c
  JOIN pg_class cl ON cl.oid=c.conrelid
  JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='clutch_genotype_options';
  IF pkname IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.clutch_genotype_options DROP CONSTRAINT '||quote_ident(pkname);
  END IF;
  EXECUTE 'ALTER TABLE public.clutch_genotype_options ADD CONSTRAINT clutch_genotype_options_pkey PRIMARY KEY (id)';
END $$;
ALTER TABLE public.clutch_genotype_options DROP CONSTRAINT IF EXISTS clutch_genotype_options_id_equals_id_uuid;
DROP INDEX IF EXISTS public.clutch_genotype_options_id_key;
ALTER TABLE public.clutch_genotype_options DROP COLUMN IF EXISTS id_uuid;

-- clutch_plan_treatments
ALTER TABLE public.clutch_plan_treatments ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.clutch_plan_treatments SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.clutch_plan_treatments ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.clutch_plan_treatments ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO $$
DECLARE pkname text;
BEGIN
  SELECT c.conname INTO pkname
  FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='clutch_plan_treatments';
  IF pkname IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.clutch_plan_treatments DROP CONSTRAINT '||quote_ident(pkname);
  END IF;
  EXECUTE 'ALTER TABLE public.clutch_plan_treatments ADD CONSTRAINT clutch_plan_treatments_pkey PRIMARY KEY (id)';
END $$;
ALTER TABLE public.clutch_plan_treatments DROP CONSTRAINT IF EXISTS clutch_plan_treatments_id_equals_id_uuid;
DROP INDEX IF EXISTS public.clutch_plan_treatments_id_key;
ALTER TABLE public.clutch_plan_treatments DROP COLUMN IF EXISTS id_uuid;

-- clutch_treatments
ALTER TABLE public.clutch_treatments ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.clutch_treatments SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.clutch_treatments ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.clutch_treatments ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO $$
DECLARE pkname text;
BEGIN
  SELECT c.conname INTO pkname
  FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='clutch_treatments';
  IF pkname IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.clutch_treatments DROP CONSTRAINT '||quote_ident(pkname);
  END IF;
  EXECUTE 'ALTER TABLE public.clutch_treatments ADD CONSTRAINT clutch_treatments_pkey PRIMARY KEY (id)';
END $$;
ALTER TABLE public.clutch_treatments DROP CONSTRAINT IF EXISTS clutch_treatments_id_equals_id_uuid;
DROP INDEX IF EXISTS public.clutch_treatments_id_key;
ALTER TABLE public.clutch_treatments DROP COLUMN IF EXISTS id_uuid;

-- clutches
ALTER TABLE public.clutches ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.clutches SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.clutches ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.clutches ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO $$
DECLARE pkname text;
BEGIN
  SELECT c.conname INTO pkname
  FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='clutches';
  IF pkname IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.clutches DROP CONSTRAINT '||quote_ident(pkname);
  END IF;
  EXECUTE 'ALTER TABLE public.clutches ADD CONSTRAINT clutches_pkey PRIMARY KEY (id)';
END $$;
ALTER TABLE public.clutches DROP CONSTRAINT IF EXISTS clutches_id_equals_id_uuid;
DROP INDEX IF EXISTS public.clutches_id_key;
ALTER TABLE public.clutches DROP COLUMN IF EXISTS id_uuid;

-- containers
ALTER TABLE public.containers ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.containers SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.containers ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.containers ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO $$
DECLARE pkname text;
BEGIN
  SELECT c.conname INTO pkname
  FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='containers';
  IF pkname IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.containers DROP CONSTRAINT '||quote_ident(pkname);
  END IF;
  EXECUTE 'ALTER TABLE public.containers ADD CONSTRAINT containers_pkey PRIMARY KEY (id)';
END $$;
ALTER TABLE public.containers DROP CONSTRAINT IF EXISTS containers_id_equals_id_uuid;
DROP INDEX IF EXISTS public.containers_id_key;
ALTER TABLE public.containers DROP COLUMN IF EXISTS id_uuid;

-- cross_instances
ALTER TABLE public.cross_instances ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.cross_instances SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.cross_instances ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.cross_instances ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO $$
DECLARE pkname text;
BEGIN
  SELECT c.conname INTO pkname
  FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='cross_instances';
  IF pkname IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.cross_instances DROP CONSTRAINT '||quote_ident(pkname);
  END IF;
  EXECUTE 'ALTER TABLE public.cross_instances ADD CONSTRAINT cross_instances_pkey PRIMARY KEY (id)';
END $$;
ALTER TABLE public.cross_instances DROP CONSTRAINT IF EXISTS cross_instances_id_equals_id_uuid;
DROP INDEX IF EXISTS public.cross_instances_id_key;
ALTER TABLE public.cross_instances DROP COLUMN IF EXISTS id_uuid;

-- crosses
ALTER TABLE public.crosses ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.crosses SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.crosses ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.crosses ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO $$
DECLARE pkname text;
BEGIN
  SELECT c.conname INTO pkname
  FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='crosses';
  IF pkname IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.crosses DROP CONSTRAINT '||quote_ident(pkname);
  END IF;
  EXECUTE 'ALTER TABLE public.crosses ADD CONSTRAINT crosses_pkey PRIMARY KEY (id)';
END $$;
ALTER TABLE public.crosses DROP CONSTRAINT IF EXISTS crosses_id_equals_id_uuid;
DROP INDEX IF EXISTS public.crosses_id_key;
ALTER TABLE public.crosses DROP COLUMN IF EXISTS id_uuid;

-- label_items
ALTER TABLE public.label_items ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.label_items SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.label_items ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.label_items ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO $$
DECLARE pkname text;
BEGIN
  SELECT c.conname INTO pkname
  FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='label_items';
  IF pkname IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.label_items DROP CONSTRAINT '||quote_ident(pkname);
  END IF;
  EXECUTE 'ALTER TABLE public.label_items ADD CONSTRAINT label_items_pkey PRIMARY KEY (id)';
END $$;
ALTER TABLE public.label_items DROP CONSTRAINT IF EXISTS label_items_id_equals_id_uuid;
DROP INDEX IF EXISTS public.label_items_id_key;
ALTER TABLE public.label_items DROP COLUMN IF EXISTS id_uuid;

-- planned_crosses
ALTER TABLE public.planned_crosses ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.planned_crosses SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.planned_crosses ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.planned_crosses ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO $$
DECLARE pkname text;
BEGIN
  SELECT c.conname INTO pkname
  FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='planned_crosses';
  IF pkname IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.planned_crosses DROP CONSTRAINT '||quote_ident(pkname);
  END IF;
  EXECUTE 'ALTER TABLE public.planned_crosses ADD CONSTRAINT planned_crosses_pkey PRIMARY KEY (id)';
END $$;
ALTER TABLE public.planned_crosses DROP CONSTRAINT IF EXISTS planned_crosses_id_equals_id_uuid;
DROP INDEX IF EXISTS public.planned_crosses_id_key;
ALTER TABLE public.planned_crosses DROP COLUMN IF EXISTS id_uuid;

-- plasmids
ALTER TABLE public.plasmids ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.plasmids SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.plasmids ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.plasmids ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO $$
DECLARE pkname text;
BEGIN
  SELECT c.conname INTO pkname
  FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='plasmids';
  IF pkname IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.plasmids DROP CONSTRAINT '||quote_ident(pkname);
  END IF;
  EXECUTE 'ALTER TABLE public.plasmids ADD CONSTRAINT plasmids_pkey PRIMARY KEY (id)';
END $$;
ALTER TABLE public.plasmids DROP CONSTRAINT IF EXISTS plasmids_id_equals_id_uuid;
DROP INDEX IF EXISTS public.plasmids_id_key;
ALTER TABLE public.plasmids DROP COLUMN IF EXISTS id_uuid;

-- rnas
ALTER TABLE public.rnas ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.rnas SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.rnas ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.rnas ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO $$
DECLARE pkname text;
BEGIN
  SELECT c.conname INTO pkname
  FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='rnas';
  IF pkname IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.rnas DROP CONSTRAINT '||quote_ident(pkname);
  END IF;
  EXECUTE 'ALTER TABLE public.rnas ADD CONSTRAINT rnas_pkey PRIMARY KEY (id)';
END $$;
ALTER TABLE public.rnas DROP CONSTRAINT IF EXISTS rnas_id_equals_id_uuid;
DROP INDEX IF EXISTS public.rnas_id_key;
ALTER TABLE public.rnas DROP COLUMN IF EXISTS id_uuid;

-- selection_labels
ALTER TABLE public.selection_labels ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.selection_labels SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.selection_labels ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.selection_labels ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO $$
DECLARE pkname text;
BEGIN
  SELECT c.conname INTO pkname
  FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='selection_labels';
  IF pkname IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.selection_labels DROP CONSTRAINT '||quote_ident(pkname);
  END IF;
  EXECUTE 'ALTER TABLE public.selection_labels ADD CONSTRAINT selection_labels_pkey PRIMARY KEY (id)';
END $$;
ALTER TABLE public.selection_labels DROP CONSTRAINT IF EXISTS selection_labels_id_equals_id_uuid;
DROP INDEX IF EXISTS public.selection_labels_id_key;
ALTER TABLE public.selection_labels DROP COLUMN IF EXISTS id_uuid;

-- tank_requests
ALTER TABLE public.tank_requests ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.tank_requests SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.tank_requests ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.tank_requests ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO $$
DECLARE pkname text;
BEGIN
  SELECT c.conname INTO pkname
  FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='tank_requests';
  IF pkname IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.tank_requests DROP CONSTRAINT '||quote_ident(pkname);
  END IF;
  EXECUTE 'ALTER TABLE public.tank_requests ADD CONSTRAINT tank_requests_pkey PRIMARY KEY (id)';
END $$;
ALTER TABLE public.tank_requests DROP CONSTRAINT IF EXISTS tank_requests_id_equals_id_uuid;
DROP INDEX IF EXISTS public.tank_requests_id_key;
ALTER TABLE public.tank_requests DROP COLUMN IF EXISTS id_uuid;

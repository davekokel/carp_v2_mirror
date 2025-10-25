-- Ensure every table used in views has an id column (mapped to id_uuid where needed);
DO $$
BEGIN
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'containers',
    'crosses',
    'label_jobs',
    'fish',
    'plasmids',
    'rnas'
  ]
  LOOP
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name=t AND column_name='id'
    ) THEN
      EXECUTE format('ALTER TABLE public.%I ADD COLUMN id uuid', t);
      EXECUTE format('UPDATE public.%I SET id = id_uuid WHERE id IS NULL', t);
      EXECUTE format('ALTER TABLE public.%I ALTER COLUMN id SET DEFAULT gen_random_uuid()', t);
    END IF;
  END LOOP;
END;
END;
$$ LANGUAGE plpgsql;

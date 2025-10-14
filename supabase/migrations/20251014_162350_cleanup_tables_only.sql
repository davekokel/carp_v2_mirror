DO $$
DECLARE t text;
BEGIN
  FOR t IN
    SELECT c.table_name
    FROM information_schema.columns c
    JOIN information_schema.tables  t
      ON t.table_schema=c.table_schema AND t.table_name=c.table_name
    WHERE c.table_schema='public'
      AND c.column_name='id_uuid'
      AND t.table_type='BASE TABLE'
  LOOP
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name=t AND column_name='id'
    ) THEN
      EXECUTE format('ALTER TABLE public.%I ADD COLUMN id uuid', t);
      EXECUTE format('UPDATE public.%I SET id = id_uuid WHERE id IS NULL', t);
      EXECUTE format('ALTER TABLE public.%I ALTER COLUMN id SET NOT NULL', t);
      EXECUTE format('ALTER TABLE public.%I ALTER COLUMN id SET DEFAULT gen_random_uuid()', t);
    END IF;

    EXECUTE format('ALTER TABLE public.%I DROP COLUMN IF EXISTS id_uuid', t);
  END LOOP;
END $$;

DO $$
DECLARE
  t text;
BEGIN
  FOR t IN
    SELECT table_name
    FROM information_schema.columns
    WHERE table_schema='public' AND column_name='id_uuid'
  LOOP
    EXECUTE format('ALTER TABLE IF EXISTS public.%I ADD COLUMN IF NOT EXISTS id uuid', t);
    EXECUTE format('UPDATE public.%I SET id=id_uuid WHERE id IS NULL', t);
    EXECUTE format('ALTER TABLE public.%I ALTER COLUMN id SET DEFAULT gen_random_uuid()', t);
    EXECUTE format('ALTER TABLE public.%I DROP COLUMN IF EXISTS id_uuid CASCADE', t);
  END LOOP;
END $$;

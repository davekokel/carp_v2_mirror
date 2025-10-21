DO $$
DECLARE pol text;
BEGIN
  FOR pol IN
    SELECT policyname
    FROM pg_policies
    WHERE schemaname='public' AND tablename='fish'
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.fish', pol);
  END LOOP;
END$$;

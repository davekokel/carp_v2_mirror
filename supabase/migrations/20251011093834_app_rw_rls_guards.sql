-- enable RLS + policies only when the table exists
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='fish') THEN
    ALTER TABLE public.fish ENABLE ROW LEVEL SECURITY;
    IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid='public.fish'::regclass AND polname='app_rw_select_fish') THEN
      CREATE POLICY app_rw_select_fish ON public.fish FOR SELECT TO app_rw USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid='public.fish'::regclass AND polname='app_rw_insert_fish') THEN
      CREATE POLICY app_rw_insert_fish ON public.fish FOR INSERT TO app_rw WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid='public.fish'::regclass AND polname='app_rw_update_fish') THEN
      CREATE POLICY app_rw_update_fish ON public.fish FOR UPDATE TO app_rw USING (true) WITH CHECK (true);
    END IF;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='transgene_alleles') THEN
    ALTER TABLE public.transgene_alleles ENABLE ROW LEVEL SECURITY;
    IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid='public.transgene_alleles'::regclass AND polname='app_rw_select_tga') THEN
      CREATE POLICY app_rw_select_tga ON public.transgene_alleles FOR SELECT TO app_rw USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid='public.transgene_alleles'::regclass AND polname='app_rw_insert_tga') THEN
      CREATE POLICY app_rw_insert_tga ON public.transgene_alleles FOR INSERT TO app_rw WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid='public.transgene_alleles'::regclass AND polname='app_rw_update_tga') THEN
      CREATE POLICY app_rw_update_tga ON public.transgene_alleles FOR UPDATE TO app_rw USING (true) WITH CHECK (true);
    END IF;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='fish_transgene_alleles') THEN
    ALTER TABLE public.fish_transgene_alleles ENABLE ROW LEVEL SECURITY;
    IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid='public.fish_transgene_alleles'::regclass AND polname='app_rw_select_fta') THEN
      CREATE POLICY app_rw_select_fta ON public.fish_transgene_alleles FOR SELECT TO app_rw USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid='public.fish_transgene_alleles'::regclass AND polname='app_rw_insert_fta') THEN
      CREATE POLICY app_rw_insert_fta ON public.fish_transgene_alleles FOR INSERT TO app_rw WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid='public.fish_transgene_alleles'::regclass AND polname='app_rw_update_fta') THEN
      CREATE POLICY app_rw_update_fta ON public.fish_transgene_alleles FOR UPDATE TO app_rw USING (true) WITH CHECK (true);
    END IF;
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw') THEN
    CREATE ROLE app_rw LOGIN;
  END IF;
END
$$ LANGUAGE plpgsql;LANGUAGE plpgsql;


GRANT USAGE ON SCHEMA public TO app_rw;
GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO app_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO app_rw;
GRANT USAGE,SELECT,UPDATE ON ALL SEQUENCES IN SCHEMA public TO app_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE,SELECT,UPDATE ON SEQUENCES TO app_rw;

ALTER TABLE public.fish ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polrelid='public.fish'::regclass AND polname='app_rw_select_fish'
  ) THEN
    CREATE POLICY app_rw_select_fish ON public.fish FOR SELECT TO app_rw USING (true);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polrelid='public.fish'::regclass AND polname='app_rw_insert_fish'
  ) THEN
    CREATE POLICY app_rw_insert_fish ON public.fish FOR INSERT TO app_rw WITH CHECK (true);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polrelid='public.fish'::regclass AND polname='app_rw_update_fish'
  ) THEN
    CREATE POLICY app_rw_update_fish ON public.fish FOR UPDATE TO app_rw USING (true) WITH CHECK (true);
  END IF;
END
$$ LANGUAGE plpgsql;LANGUAGE plpgsql;


ALTER TABLE public.transgene_alleles ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polrelid='public.transgene_alleles'::regclass AND polname='app_rw_select_tga'
  ) THEN
    CREATE POLICY app_rw_select_tga ON public.transgene_alleles FOR SELECT TO app_rw USING (true);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polrelid='public.transgene_alleles'::regclass AND polname='app_rw_insert_tga'
  ) THEN
    CREATE POLICY app_rw_insert_tga ON public.transgene_alleles FOR INSERT TO app_rw WITH CHECK (true);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polrelid='public.transgene_alleles'::regclass AND polname='app_rw_update_tga'
  ) THEN
    CREATE POLICY app_rw_update_tga ON public.transgene_alleles FOR UPDATE TO app_rw USING (true) WITH CHECK (true);
  END IF;
END
$$ LANGUAGE plpgsql;LANGUAGE plpgsql;


ALTER TABLE public.fish_transgene_alleles ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polrelid='public.fish_transgene_alleles'::regclass AND polname='app_rw_select_fta'
  ) THEN
    CREATE POLICY app_rw_select_fta ON public.fish_transgene_alleles FOR SELECT TO app_rw USING (true);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polrelid='public.fish_transgene_alleles'::regclass AND polname='app_rw_insert_fta'
  ) THEN
    CREATE POLICY app_rw_insert_fta ON public.fish_transgene_alleles FOR INSERT TO app_rw WITH CHECK (true);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polrelid='public.fish_transgene_alleles'::regclass AND polname='app_rw_update_fta'
  ) THEN
    CREATE POLICY app_rw_update_fta ON public.fish_transgene_alleles FOR UPDATE TO app_rw USING (true) WITH CHECK (true);
  END IF;
END
$$ LANGUAGE plpgsql;LANGUAGE plpgsql;



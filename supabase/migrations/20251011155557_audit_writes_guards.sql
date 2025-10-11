DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='fish') THEN
    PERFORM audit.attach_writes('public.fish'::regclass);
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='transgene_alleles') THEN
    PERFORM audit.attach_writes('public.transgene_alleles'::regclass);
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='fish_transgene_alleles') THEN
    PERFORM audit.attach_writes('public.fish_transgene_alleles'::regclass);
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='containers') THEN
    PERFORM audit.attach_writes('public.containers'::regclass);
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='fish_tank_memberships') THEN
    PERFORM audit.attach_writes('public.fish_tank_memberships'::regclass);
  END IF;
END$$;

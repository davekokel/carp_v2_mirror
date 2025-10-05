DO $$
BEGIN
  IF to_regclass('public.vw_fish_overview') IS NULL AND to_regclass('public.v_fish_overview') IS NOT NULL THEN
    EXECUTE 'ALTER VIEW public.v_fish_overview RENAME TO vw_fish_overview';
  END IF;
END$$;

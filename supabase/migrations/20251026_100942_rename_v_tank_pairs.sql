DO $$
BEGIN
  IF to_regclass('public.v_tank_pairs') IS NULL
     AND to_regclass('public.vw_tank_pairs') IS NOT NULL THEN
    EXECUTE 'ALTER VIEW public.vw_tank_pairs RENAME TO v_tank_pairs';
  ELSE
    IF to_regclass('public.vw_tank_pairs') IS NOT NULL THEN
      EXECUTE 'DROP VIEW public.vw_tank_pairs';
    END IF;
  END IF;
END
$$;

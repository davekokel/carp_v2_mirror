DO $$
BEGIN
  IF to_regclass('public.plasmids') IS NOT NULL THEN
    -- original statements would run here when plasmids exists
    NULL;
  END IF;
END
$$;

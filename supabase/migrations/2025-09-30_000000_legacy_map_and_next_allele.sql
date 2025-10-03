DO $$
BEGIN
  IF to_regclass('public.transgene_alleles') IS NOT NULL THEN
    -- placeholder: only run when canonical table exists
  END IF;
END
$$;

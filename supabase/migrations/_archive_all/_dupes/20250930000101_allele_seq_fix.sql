DO $$
BEGIN
  IF to_regclass('public.transgene_alleles') IS NOT NULL THEN
    -- placeholder: run seq fix only when canonical table exists
  END IF;
END
$$;

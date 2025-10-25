DO $$
BEGIN
  IF to_regclass('public.transgene_alleles') IS NOT NULL THEN
    -- placeholder: run legacy-map logic only when canonical table exists
    -- keep empty for now
  END IF;
END
$$;

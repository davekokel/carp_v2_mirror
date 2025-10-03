DO $$
BEGIN
  IF to_regclass('public.fish_transgene_alleles') IS NOT NULL THEN
    -- original zygosity default/check adjustments would go here
    -- keep as no-op on fresh locals where the table isn't present
    NULL;
  END IF;
END
$$;

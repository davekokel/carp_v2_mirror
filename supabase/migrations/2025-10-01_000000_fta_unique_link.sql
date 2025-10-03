DO $$
BEGIN
  IF to_regclass('public.fish_transgene_alleles') IS NOT NULL THEN
    -- original adjustment would run here; guarded for from-zero locals
    -- keep as no-op when table is missing
    NULL;
  END IF;
END
$$;

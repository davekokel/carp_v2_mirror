DO $$
BEGIN
  IF to_regclass('public.fish_transgene_alleles') IS NOT NULL THEN
    -- created_at
    BEGIN
      ALTER TABLE public.fish_transgene_alleles
        ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();
    EXCEPTION WHEN duplicate_column THEN
      -- ignore
    END;

    -- created_by (nullable; add if missing)
    BEGIN
      ALTER TABLE public.fish_transgene_alleles
        ADD COLUMN IF NOT EXISTS created_by text;
    EXCEPTION WHEN duplicate_column THEN
      -- ignore
    END;
  END IF;
END
$$;

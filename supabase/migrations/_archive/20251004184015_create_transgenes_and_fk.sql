BEGIN;

-- 1) Base table for transgenes (minimal; add columns later if needed)
CREATE TABLE IF NOT EXISTS public.transgenes (
    transgene_base_code text PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text
);

-- 2) Add FK from transgene_alleles -> transgenes if it isn't present
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.transgene_alleles'::regclass
      AND conname  = 'fk_transgene_alleles_base'
  ) THEN
    -- Only add if the column exists (it should in your schema)
    IF EXISTS (
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema='public' AND table_name='transgene_alleles'
        AND column_name='transgene_base_code'
    ) THEN
      ALTER TABLE public.transgene_alleles
        ADD CONSTRAINT fk_transgene_alleles_base
        FOREIGN KEY (transgene_base_code)
        REFERENCES public.transgenes(transgene_base_code)
        ON DELETE CASCADE;
    END IF;
  END IF;
END$$;

COMMIT;

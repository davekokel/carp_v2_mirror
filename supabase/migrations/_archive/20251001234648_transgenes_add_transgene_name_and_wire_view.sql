-- Guard-safe: ensure a minimal transgenes table exists, then add transgene_name if missing.
DO $$
BEGIN
  -- Create a minimal transgenes table if it isn't present.
  IF to_regclass('public.transgenes') IS NULL THEN
    CREATE TABLE public.transgenes (
      transgene_base_code text PRIMARY KEY,
      transgene_name      text
    );
  END IF;

  -- Add the human-friendly name column if it's not there yet (idempotent).
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='transgenes'
      AND column_name='transgene_name'
  ) THEN
    ALTER TABLE public.transgenes
      ADD COLUMN transgene_name text;
  END IF;

  -- (Optional wiring to views is intentionally omitted here to avoid introducing new deps.)
END
$$;

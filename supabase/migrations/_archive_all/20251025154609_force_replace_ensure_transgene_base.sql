BEGIN;

-- Drop the old body explicitly so there’s no ambiguity.
DROP FUNCTION IF EXISTS public.ensure_transgene_base(text);

-- Recreate with dynamic SQL (no references to a non-existent column).
CREATE FUNCTION public.ensure_transgene_base(p_base text)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  v_col text;
  v_sql text;
BEGIN
  -- Detect which base-code column exists.
  SELECT CASE
           WHEN EXISTS (
             SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='transgenes'
               AND column_name='transgene_base_code'
           ) THEN 'transgene_base_code'
           WHEN EXISTS (
             SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='transgenes'
               AND column_name='base_code'
           ) THEN 'base_code'
           ELSE NULL
         END
    INTO v_col;

  IF v_col IS NULL THEN
    RAISE EXCEPTION 'transgenes table missing base-code column (expected transgene_base_code or base_code)';
  END IF;

  -- Insert base row if missing; conflict on the discovered column.
  v_sql := format(
    'INSERT INTO public.transgenes (%I) VALUES ($1)
     ON CONFLICT (%I) DO NOTHING',
    v_col, v_col
  );
  EXECUTE v_sql USING p_base;
END
$$;

COMMIT;

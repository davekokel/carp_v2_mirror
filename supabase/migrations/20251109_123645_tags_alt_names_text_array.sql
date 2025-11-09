BEGIN;
ALTER TABLE public.tags ADD COLUMN IF NOT EXISTS alt_names text[];
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tags' AND column_name='alt_names' AND data_type='text'
  ) THEN
    EXECUTE $x$
      ALTER TABLE public.tags
      ALTER COLUMN alt_names TYPE text[]
      USING CASE
        WHEN alt_names IS NULL OR btrim(alt_names)='' THEN NULL
        WHEN alt_names LIKE '{%}' THEN alt_names::text[]
        ELSE string_to_array(alt_names, ',')
      END
    $x$;
  END IF;
END$$;
COMMIT;

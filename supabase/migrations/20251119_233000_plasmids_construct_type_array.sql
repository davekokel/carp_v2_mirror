BEGIN;

ALTER TABLE public.plasmids
    ALTER COLUMN construct_type DROP DEFAULT;

-- If the column already exists as text, convert to text[].
ALTER TABLE public.plasmids
    ALTER COLUMN construct_type TYPE text[]
    USING
      CASE
        WHEN construct_type IS NULL OR construct_type = '' THEN ARRAY[]::text[]
        ELSE ARRAY[construct_type]::text[]
      END;

COMMIT;

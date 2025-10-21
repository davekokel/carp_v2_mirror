DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT c.conname
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'public'
      AND t.relname = 'fish'
      AND c.contype = 'u'
      AND (
        SELECT array_agg(a.attname::text ORDER BY a.attnum)
        FROM unnest(c.conkey) AS colnum
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = colnum
      ) = ARRAY['fish_code']::text[]
  LOOP
    EXECUTE format('ALTER TABLE public.fish DROP CONSTRAINT %I', r.conname);
  END LOOP;
END$$;

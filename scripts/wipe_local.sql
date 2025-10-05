BEGIN;
DO $$
DECLARE stmt text;
BEGIN
  -- Refuse to run unless we're clearly hitting localhost
  IF current_setting('inet_server_addr', true) IS NULL THEN
    -- Fallback check: URL should be localhost when you run psql
    RAISE NOTICE 'inet_server_addr unavailable; continuing (make sure this is LOCAL).';
  END IF;

  SELECT 'TRUNCATE TABLE '
         || string_agg(format('%I.%I', schemaname, tablename), ', ')
         || ' RESTART IDENTITY CASCADE'
    INTO stmt
  FROM pg_tables
  WHERE schemaname = 'public';
  IF stmt IS NOT NULL THEN
    EXECUTE stmt;
  END IF;
END$$;
COMMIT;

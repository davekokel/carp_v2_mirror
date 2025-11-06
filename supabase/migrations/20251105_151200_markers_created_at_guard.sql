BEGIN;
DO $$
BEGIN
  RAISE NOTICE '151200: superseded by v4 marker/view migrations — no-op';
END$$;
COMMIT;

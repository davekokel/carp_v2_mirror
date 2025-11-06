BEGIN;
DO $$
BEGIN
  RAISE NOTICE '151100: superseded by v4 marker/view migrations — no-op';
END$$;
COMMIT;

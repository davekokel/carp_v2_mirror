BEGIN;
DO $$
BEGIN
  RAISE NOTICE '181530: deprecated step superseded by later migrations — no-op';
END$$;
COMMIT;

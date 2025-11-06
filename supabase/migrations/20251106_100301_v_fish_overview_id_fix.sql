BEGIN;
DO $$
BEGIN
  RAISE NOTICE '100301: v_fish_overview_id already updated by 100300 — no-op';
END$$;
COMMIT;

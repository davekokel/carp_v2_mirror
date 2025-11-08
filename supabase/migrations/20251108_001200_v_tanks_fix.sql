BEGIN;
-- No-op: v_tanks is already defined earlier; v_tank_pairs depends on it.
-- Keeping this migration empty avoids dependency drops mid-chain.
COMMIT;

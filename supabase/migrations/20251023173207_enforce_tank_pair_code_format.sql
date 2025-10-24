BEGIN;
-- Ensure codes look like TP-FP-YYNNNN-<n> (FP part may include hyphens)
ALTER TABLE public.tank_pairs
  DROP CONSTRAINT IF EXISTS chk_tank_pair_code_format,
  ADD CONSTRAINT chk_tank_pair_code_format
  CHECK ( tank_pair_code ~ '^TP-([A-Za-z0-9_-]+)-[0-9]+$' );
COMMIT;

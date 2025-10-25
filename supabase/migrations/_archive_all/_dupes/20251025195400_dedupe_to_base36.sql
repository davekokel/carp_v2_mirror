BEGIN;
-- Remove redundant overload; keep the bigint canonical version
DROP FUNCTION IF EXISTS public.to_base36(integer);
COMMIT;

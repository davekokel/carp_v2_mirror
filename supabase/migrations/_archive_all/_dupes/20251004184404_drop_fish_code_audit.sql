BEGIN;
-- Drop audit trigger & function if we created them earlier
DROP TRIGGER IF EXISTS trg_fish_code_audit_noncompact ON public.fish;
DROP FUNCTION IF EXISTS public.fish_code_audit_noncompact();

-- Optional: keep or drop the audit table (uncomment to drop)
-- DROP TABLE IF EXISTS public.fish_code_audit;

COMMIT;

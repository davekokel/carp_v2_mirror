BEGIN;

-- Drop the trigger on clutch_instances if it exists
DROP TRIGGER IF EXISTS trg_clutch_default_treated ON public.clutch_instances;
DROP TRIGGER IF EXISTS clutch_default_treated ON public.clutch_instances;

-- Drop the trigger function itself if it exists
DROP FUNCTION IF EXISTS public.trg_clutch_default_treated();

COMMIT;

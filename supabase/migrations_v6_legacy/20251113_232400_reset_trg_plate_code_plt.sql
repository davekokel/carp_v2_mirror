BEGIN;

-- Drop any existing trigger that uses the old function
DROP TRIGGER IF EXISTS zzz_plate_code_plt_yyyymmdd ON public.plates;
DROP TRIGGER IF EXISTS trg_plate_code_plt_yyyymmdd ON public.plates;

-- Drop the old function completely to get rid of any cached definition
DROP FUNCTION IF EXISTS public.trg_plate_code_plt_yyyymmdd();

-- Recreate a clean trigger function with no format()
CREATE FUNCTION public.trg_plate_code_plt_yyyymmdd()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  d text;
  n int;
BEGIN
  -- Only set/override if code is empty or legacy-style (format%)
  IF NEW.plate_code IS NULL OR NEW.plate_code = '' OR NEW.plate_code LIKE 'format%' THEN
    d := to_char(COALESCE(NEW.created_at, now())::date, 'YYYYMMDD');

    SELECT COALESCE(
             MAX( (regexp_match(plate_code, 'PLT-'||d||'-#(\\d+)$'))[1]::int ),
             0
           )
      INTO n
      FROM public.plates
     WHERE plate_code LIKE 'PLT-'||d||'-%';

    -- Build PLT-YYYYMMDD-#NN using lpad (no format())
    NEW.plate_code := 'PLT-' || d || '-#' || lpad((n + 1)::text, 2, '0');
  END IF;

  RETURN NEW;
END
$$;

-- Re-attach the trigger
CREATE TRIGGER zzz_plate_code_plt_yyyymmdd
BEFORE INSERT ON public.plates
FOR EACH ROW
EXECUTE FUNCTION public.trg_plate_code_plt_yyyymmdd();

COMMIT;

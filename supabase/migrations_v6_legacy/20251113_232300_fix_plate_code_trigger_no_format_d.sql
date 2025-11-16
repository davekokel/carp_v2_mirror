BEGIN;

-- Replace the trigger function to avoid unsupported %d in format()
CREATE OR REPLACE FUNCTION public.trg_plate_code_plt_yyyymmdd()
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

    -- build PLT-YYYYMMDD-#NN without format(), using lpad for zero padding
    NEW.plate_code := 'PLT-' || d || '-#' || lpad((n + 1)::text, 2, '0');
  END IF;

  RETURN NEW;
END
$$;

-- Optional: fix any existing PLT-YYYYMMDD-#N (no zero) to PLT-YYYYMMDD-#0N
UPDATE public.plates
SET plate_code = regexp_replace(plate_code, '#([0-9])$', '#0\\1')
WHERE plate_code ~ '^PLT-[0-9]{8}-#[0-9]$';

COMMIT;

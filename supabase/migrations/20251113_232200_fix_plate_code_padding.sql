BEGIN;

-- Replace the trigger function to use %02d (no space before the number)
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

    NEW.plate_code := format('PLT-%s-#%02d', d, n + 1);
  END IF;

  RETURN NEW;
END
$$;

-- Clean up any existing codes with a stray space after '#'
UPDATE public.plates
SET plate_code = replace(plate_code, '# ', '#')
WHERE plate_code LIKE 'PLT-%# %';

COMMIT;

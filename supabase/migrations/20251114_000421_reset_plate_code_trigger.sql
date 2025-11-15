BEGIN;

-- Nuke any existing plate-code triggers that might reference this function
DROP TRIGGER IF EXISTS trg_plate_code_plt_yyyymmdd ON public.plates;
DROP TRIGGER IF EXISTS zzz_plate_code_plt_yyyymmdd ON public.plates;

-- Drop the function itself, allowing dependent objects to go
DROP FUNCTION IF EXISTS public.trg_plate_code_plt_yyyymmdd() CASCADE;

-- Recreate the function with the correct behavior
CREATE FUNCTION public.trg_plate_code_plt_yyyymmdd()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_date text;
  v_base text;
  v_next int;
BEGIN
  -- If caller already supplied a plate_code, keep it
  IF NEW.plate_code IS NOT NULL AND NEW.plate_code <> '' THEN
    RETURN NEW;
  END IF;

  -- Date portion for this plate
  v_date := to_char(COALESCE(NEW.created_at, now()), 'YYYYMMDD');
  v_base := 'PLT-' || v_date || '-#';

  -- Find max numeric suffix for this date, then increment
  SELECT COALESCE(MAX(sub.n), 0) + 1
  INTO v_next
  FROM (
    SELECT (regexp_match(plate_code, '#(\\d+)$'))[1]::int AS n
    FROM public.plates
    WHERE plate_code LIKE v_base || '%'
  ) AS sub;

  NEW.plate_code := v_base || lpad(v_next::text, 2, '0');

  RETURN NEW;
END;
$$;

-- Attach a single canonical trigger
CREATE TRIGGER trg_plate_code_plt_yyyymmdd
BEFORE INSERT ON public.plates
FOR EACH ROW
EXECUTE FUNCTION public.trg_plate_code_plt_yyyymmdd();

COMMIT;

BEGIN;

-- Day-scoped, 3-digit zero-padded code: PLT-YYYYMMDD-001 .. -100
-- Concurrency-safe via an advisory lock keyed by the date.
CREATE OR REPLACE FUNCTION public.plate_code_next()
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
  v_day   text;   -- YYYYMMDD
  v_next  int;
BEGIN
  v_day := to_char(now(), 'YYYYMMDD');

  -- Prevent concurrent callers from generating the same number for this day
  PERFORM pg_advisory_xact_lock( hashtext('plate_code:' || v_day) );

  -- Compute the next daily number by scanning existing codes for this day
  SELECT COALESCE(
           MAX( (regexp_match(plate_code, '-([0-9]{3})$'))[1]::int ),
           0
         )
    INTO v_next
  FROM public.plates
  WHERE plate_code LIKE 'PLT-' || v_day || '-%';

  IF v_next >= 100 THEN
    RAISE EXCEPTION 'Daily plate-code limit (100) reached for %', v_day
      USING ERRCODE = 'check_violation';
  END IF;

  v_next := v_next + 1;

  RETURN 'PLT-' || v_day || '-' || lpad(v_next::text, 3, '0');
END
$$;

COMMIT;

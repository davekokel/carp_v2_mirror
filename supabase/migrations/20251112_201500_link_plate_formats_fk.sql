BEGIN;

DO $$
DECLARE
  missing text;
BEGIN
  IF to_regclass('public.plates') IS NULL
     OR to_regclass('public.plate_formats') IS NULL THEN
    RETURN;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.plates'::regclass
      AND contype = 'f'
      AND conname = 'fk_plates_format_code'
  ) THEN
    RETURN;
  END IF;

  SELECT p.format_code
    INTO missing
  FROM public.plates p
  LEFT JOIN public.plate_formats pf
    ON pf.code = p.format_code
  WHERE p.format_code IS NOT NULL
    AND pf.code IS NULL
  LIMIT 1;

  IF missing IS NOT NULL THEN
    RAISE EXCEPTION
      'Cannot add FK plates.format_code -> plate_formats.code; missing plate_format code=%', missing;
  END IF;

  ALTER TABLE public.plates
    ADD CONSTRAINT fk_plates_format_code
      FOREIGN KEY (format_code)
      REFERENCES public.plate_formats(code);
END$$;

COMMIT;

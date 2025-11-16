BEGIN;

DO $$
BEGIN
  -- Bail out quietly if either table doesn't exist in this env
  IF to_regclass('public.plates') IS NULL
     OR to_regclass('public.plate_formats') IS NULL THEN
    RETURN;
  END IF;

  -- If the FK already exists, do nothing
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.plates'::regclass
      AND contype = 'f'
      AND conname = 'fk_plates_format_code'
  ) THEN
    RETURN;
  END IF;

  -- Safety check: no orphan format_code values
  IF EXISTS (
    SELECT 1
    FROM public.plates p
    LEFT JOIN public.plate_formats pf
      ON pf.code = p.format_code
    WHERE p.format_code IS NOT NULL
      AND pf.code IS NULL
  ) THEN
    RAISE EXCEPTION
      'Cannot add FK plates.format_code -> plate_formats.code; missing plate_formats row(s)';
  END IF;

  -- Add the real FK
  ALTER TABLE public.plates
    ADD CONSTRAINT fk_plates_format_code
      FOREIGN KEY (format_code)
      REFERENCES public.plate_formats(code);
END$$;

COMMIT;

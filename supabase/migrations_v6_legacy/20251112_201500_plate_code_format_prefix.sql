BEGIN;

-- Clean out any older generators so we own the logic
DROP TRIGGER IF EXISTS trg_plate_code_generate ON public.plates;
DROP FUNCTION IF EXISTS public.plate_code_simple_generate();
DROP FUNCTION IF EXISTS public.plate_code_generate();
DROP FUNCTION IF EXISTS public._slugify_plate_name(text);

-- Sequence for short codes: format001, format002, ...
CREATE SEQUENCE IF NOT EXISTS public.plate_format_seq;

-- Trigger function: set plate_code if NULL; do not touch any other columns
CREATE OR REPLACE FUNCTION public.plate_code_format_generate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.plate_code IS NULL THEN
    NEW.plate_code := 'format' || lpad(nextval('public.plate_format_seq')::text, 3, '0');
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_plate_code_generate
BEFORE INSERT ON public.plates
FOR EACH ROW
EXECUTE FUNCTION public.plate_code_format_generate();

-- Backfill any existing NULL plate_code rows safely
UPDATE public.plates
SET plate_code = 'format' || lpad(nextval('public.plate_format_seq')::text, 3, '0')
WHERE plate_code IS NULL;

-- Ensure uniqueness on plate_code
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.plates'::regclass AND conname='uq_plates_plate_code'
  ) THEN
    ALTER TABLE public.plates ADD CONSTRAINT uq_plates_plate_code UNIQUE (plate_code);
  END IF;
END$$;

COMMIT;

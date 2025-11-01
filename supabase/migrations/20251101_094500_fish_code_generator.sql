BEGIN;

-- Sequence for fish codes (idempotent)
CREATE SEQUENCE IF NOT EXISTS public.seq_fish_code START 1;

-- Trigger function: assign fish_code if missing
CREATE OR REPLACE FUNCTION public.ensure_fish_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  n bigint;
BEGIN
  IF NEW.fish_code IS NULL OR NEW.fish_code = '' THEN
    n := nextval('public.seq_fish_code');
    -- Format: FSH-000001, FSH-000002, ...
    NEW.fish_code := 'FSH-' || to_char(n, 'FM000000');
  END IF;
  RETURN NEW;
END;
$$;

-- Attach trigger (recreate safely)
DROP TRIGGER IF EXISTS trg_fish_ensure_code ON public.fish;
CREATE TRIGGER trg_fish_ensure_code
BEFORE INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.ensure_fish_code();

COMMIT;

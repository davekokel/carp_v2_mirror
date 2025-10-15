BEGIN;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'uq_fish_fish_code'
      AND conrelid = 'public.fish'::regclass
  ) THEN
    ALTER TABLE public.fish ADD CONSTRAINT uq_fish_fish_code UNIQUE (fish_code);
  END IF;
END$$;

CREATE OR REPLACE FUNCTION public.fish_before_insert_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.fish_code IS NULL OR btrim(NEW.fish_code) = '' THEN
    NEW.fish_code := public.make_fish_code_compact();
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_fish_before_insert_code ON public.fish;

CREATE TRIGGER trg_fish_before_insert_code
BEFORE INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.fish_before_insert_code();

COMMIT;

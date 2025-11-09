BEGIN;

CREATE OR REPLACE FUNCTION public.to_base36(n bigint)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
  chars text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  result text := '';
  q bigint := n;
BEGIN
  IF q <= 0 THEN
    RETURN '0';
  END IF;
  WHILE q > 0 LOOP
    result := substr(chars, (q % 36) + 1, 1) || result;
    q := q / 36;
  END LOOP;
  RETURN result;
END;
$$;

CREATE SEQUENCE IF NOT EXISTS public.seq_fish_code START 1;

CREATE OR REPLACE FUNCTION public.trg_set_fish_code_base36()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.fish_code IS NULL OR btrim(NEW.fish_code) = '' THEN
    NEW.fish_code := 'FSH-' || lpad(upper(public.to_base36(nextval('public.seq_fish_code'))), 8, '0');
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fish_code_default ON public.fish;
CREATE TRIGGER trg_fish_code_default
BEFORE INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.trg_set_fish_code_base36();

COMMIT;

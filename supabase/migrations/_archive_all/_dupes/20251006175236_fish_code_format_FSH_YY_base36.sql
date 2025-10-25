BEGIN;

-- 1) Ensure the sequence exists (no backfill)
CREATE SEQUENCE IF NOT EXISTS public.fish_code_seq;

-- 2) Trigger function: set fish_code as FSH-YYXXXX (base36, 4 chars), only if missing/malformed
CREATE OR REPLACE FUNCTION public.fish_bi_set_fish_code()
RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  v bigint;
  r int;
  s text := '';
  yy text;
  digits constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
BEGIN
  IF NEW.fish_code IS NULL OR NEW.fish_code !~ '^FSH-\d{2}[0-9A-Z]{4}$' THEN
    -- two-digit UTC year
    yy := to_char(timezone('UTC', now()), 'YY');

    -- next sequence value, convert to base36 (uppercase)
    v := nextval('public.fish_code_seq');
    IF v = 0 THEN
      s := '0';
    ELSE
      WHILE v > 0 LOOP
        r := (v % 36)::int;
        s := substr(digits, r+1, 1) || s;
        v := v / 36;
      END LOOP;
    END IF;

    -- left-pad to 4
    s := lpad(s, 4, '0');

    NEW.fish_code := 'FSH-' || yy || s;
  END IF;

  RETURN NEW;
END;
$$;

-- 3) Attach the trigger (replace if it already exists)
DROP TRIGGER IF EXISTS bi_set_fish_code ON public.fish;
CREATE TRIGGER bi_set_fish_code
BEFORE INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.fish_bi_set_fish_code();

COMMIT;

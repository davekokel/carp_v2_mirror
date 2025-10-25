BEGIN;

-- A) Compact code helpers (safe to re-create)
CREATE SEQUENCE IF NOT EXISTS public.fish_code_seq START 1;

CREATE OR REPLACE FUNCTION public._to_base36(n bigint, pad int)
RETURNS text LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
  chars CONSTANT text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  x bigint := n; out text := ''; d int;
BEGIN
  IF x < 0 THEN RAISE EXCEPTION 'negative not allowed'; END IF;
  IF x = 0 THEN out := '0';
  ELSE
    WHILE x > 0 LOOP d := (x % 36); out := substr(chars,d+1,1) || out; x := x / 36; END LOOP;
  END IF;
  IF length(out) < pad THEN out := lpad(out, pad, '0'); END IF;
  RETURN out;
END $$;

CREATE OR REPLACE FUNCTION public.make_fish_code_compact()
RETURNS text LANGUAGE sql AS $$
  SELECT 'FSH-' || to_char(current_date,'YY') || public._to_base36(nextval('public.fish_code_seq'), 4)
$$;

-- B) Remove ALL existing user triggers on fish (legacy & prior versions);
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT tgname FROM pg_trigger
    WHERE tgrelid='public.fish'::regclass AND NOT tgisinternal
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.fish', r.tgname);
  END LOOP;
END$$;

-- C) (Re)install single compact BEFORE INSERT trigger
CREATE OR REPLACE FUNCTION public.fish_before_insert_code()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.fish_code IS NULL OR btrim(NEW.fish_code) = '' THEN
    NEW.fish_code := public.make_fish_code_compact();
  END IF;
  RETURN NEW;
END
$$;

CREATE TRIGGER trg_fish_before_insert_code
BEFORE INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.fish_before_insert_code();

-- D) Drop obsolete generators if present (cleanup);
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='trg_fish_set_code' AND pronamespace='public'::regnamespace)
  THEN EXECUTE 'DROP FUNCTION public.trg_fish_set_code() CASCADE'; END IF;

  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='fish_code_next' AND pronamespace='public'::regnamespace)
  THEN EXECUTE 'DROP FUNCTION public.fish_code_next() CASCADE'; END IF;

  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='gen_fish_code' AND pronamespace='public'::regnamespace)
  THEN EXECUTE 'DROP FUNCTION public.gen_fish_code(timestamp with time zone) CASCADE'; END IF;
END$$;

-- E) Format check (compact);
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='ck_fish_fish_code_format' AND conrelid='public.fish'::regclass
  ) THEN
    ALTER TABLE public.fish
      ADD CONSTRAINT ck_fish_fish_code_format
      CHECK (fish_code ~ '^FSH-[0-9]{2}[0-9A-Z]{4,}$');
  END IF;
END$$;

COMMIT;

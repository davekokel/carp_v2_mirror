BEGIN;

-- Helper: base36 with left-pad
CREATE OR REPLACE FUNCTION public._to_base36(n bigint, pad int)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE AS $$
DECLARE
  chars CONSTANT text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  x bigint := n;
  out text := '';
BEGIN
  IF x < 0 THEN RAISE EXCEPTION 'negative not allowed'; END IF;
  IF x = 0 THEN out := '0';
  ELSE
    WHILE x > 0 LOOP
      out := substr(chars, (x % 36)+1, 1) || out;
      x := x / 36;
    END LOOP;
  END IF;
  IF length(out) < pad THEN
    out := lpad(out, pad, '0');
  END IF;
  RETURN out;
END $$;

-- Per-year counters (year → n), idempotent
CREATE TABLE IF NOT EXISTS public.fish_year_counters (
  year int PRIMARY KEY,
  n    bigint NOT NULL DEFAULT 0
);

-- Generator: FSH-YY + base36(per-year counter, min 4 chars)
CREATE OR REPLACE FUNCTION public.make_fish_code_yy_seq36(ts timestamptz DEFAULT now())
RETURNS text
LANGUAGE plpgsql AS $$
DECLARE
  yy_i int  := extract(year from ts)::int;
  yy   text := to_char(ts, 'YY');
  k    bigint;
BEGIN
  -- row-level, concurrency-safe bump
  INSERT INTO public.fish_year_counters(year, n)
  VALUES (yy_i, 1)
  ON CONFLICT (year) DO UPDATE
    SET n = public.fish_year_counters.n + 1
  RETURNING n INTO k;

  RETURN 'FSH-' || yy || public._to_base36(k, 4);
END $$;

-- BEFORE INSERT trigger: fill when blank or non-matching
CREATE OR REPLACE FUNCTION public.fish_before_insert_code()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.fish_code IS NULL
     OR btrim(NEW.fish_code) = ''
     OR NEW.fish_code !~ '^FSH-[0-9]{2}[0-9A-Z]{4,}$' THEN
    NEW.fish_code := public.make_fish_code_yy_seq36(now());
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_fish_before_insert_code ON public.fish;
CREATE TRIGGER trg_fish_before_insert_code
BEFORE INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.fish_before_insert_code();

-- Tight CHECK to enforce the format
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='ck_fish_fish_code_format' AND conrelid='public.fish'::regclass
  ) THEN
    ALTER TABLE public.fish DROP CONSTRAINT ck_fish_fish_code_format;
  END IF;
  ALTER TABLE public.fish
    ADD CONSTRAINT ck_fish_fish_code_format
    CHECK (fish_code ~ '^FSH-[0-9]{2}[0-9A-Z]{4,}$');
END$$;

COMMIT;

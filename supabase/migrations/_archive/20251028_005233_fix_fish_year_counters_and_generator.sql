-- Ensure the counter table has next_num and seed it if needed
DO $$
BEGIN
  IF to_regclass('public.fish_year_counters') IS NULL THEN
    CREATE TABLE public.fish_year_counters (
      year int PRIMARY KEY,
      next_num int NOT NULL DEFAULT 1
    );
  ELSIF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish_year_counters'
      AND column_name='next_num'
  ) THEN
    ALTER TABLE public.fish_year_counters ADD COLUMN next_num int NOT NULL DEFAULT 1;
  END IF;
END$$;

-- Normalize any NULLs (paranoid)
UPDATE public.fish_year_counters SET next_num = 1 WHERE next_num IS NULL;

-- Recreate the authoritative generator FSH-YYNNNNN
CREATE OR REPLACE FUNCTION public.gen_fish_code(p_when timestamptz DEFAULT now())
RETURNS text
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  y  int  := EXTRACT(YEAR FROM p_when)::int;
  yy text := to_char(p_when, 'YY');
  n  int;
BEGIN
  INSERT INTO public.fish_year_counters(year, next_num)
  VALUES (y, 1)
  ON CONFLICT (year) DO NOTHING;

  UPDATE public.fish_year_counters
     SET next_num = next_num + 1
   WHERE year = y
   RETURNING next_num - 1 INTO n;

  RETURN 'FSH-' || yy || to_char(n, 'FM00000');
END
$$;

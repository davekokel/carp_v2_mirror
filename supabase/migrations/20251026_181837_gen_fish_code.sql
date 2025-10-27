-- Create a sequence for fish codes (hex suffix), if missing
CREATE SEQUENCE IF NOT EXISTS public.fish_code_seq START 0 MINVALUE 0;

-- Initialize the sequence to the current max seen in fish (if any)
DO $$
DECLARE
  max_hex bigint;
BEGIN
  SELECT COALESCE(MAX( ('x' || regexp_replace(fish_code, '^FSH-',''))::bit(32)::bigint ), -1)
  INTO max_hex
  FROM public.fish
  WHERE fish_code ~ '^FSH-[0-9A-Fa-f]+$';

  IF max_hex IS NOT NULL AND max_hex >= 0 THEN
    PERFORM setval('public.fish_code_seq', max_hex, true);
  END IF;
END
$$;

-- Generate a unique fish_code like FSH-25000A (hex), retry on race
CREATE OR REPLACE FUNCTION public.gen_fish_code()
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
  try int := 0;
  suffix text;
  code text;
BEGIN
  LOOP
    try := try + 1;
    suffix := upper(to_hex(nextval('public.fish_code_seq')));
    code := 'FSH-' || suffix;

    -- ensure uniqueness
    IF NOT EXISTS (SELECT 1 FROM public.fish WHERE fish_code = code) THEN
      RETURN code;
    END IF;

    IF try > 100 THEN
      RAISE EXCEPTION 'gen_fish_code(): could not allocate unique code after % attempts', try;
    END IF;
  END LOOP;
END
$$;

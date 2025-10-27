BEGIN;

-- Make the code generator a no-op if fish_code was provided explicitly
CREATE OR REPLACE FUNCTION public.bi_set_fish_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.fish_code IS NOT NULL AND length(trim(NEW.fish_code)) > 0 THEN
    RETURN NEW;
  END IF;

  -- generate code only when missing (keep your existing scheme/prefix/counter)
  -- Example: use existing sequence or table logic; here’s a safe fallback:
  IF NEW.fish_code IS NULL OR NEW.fish_code = '' THEN
    NEW.fish_code := (
      WITH n AS (
        SELECT COALESCE(
          MAX( (regexp_replace(fish_code, '^FSH-([0-9A-F]+)$', '\1'))::text ),
          '250000'
        ) AS last -- replace with your real allocator if you have one
        FROM public.fish
        WHERE fish_code ~ '^FSH-[0-9A-F]+$'
      )
      SELECT 'FSH-' || to_char( (0x'|| (SELECT last FROM n) || ')::bit(28)::int + 1, 'FM00000X')
    );
  END IF;

  RETURN NEW;
END
$$;

-- Ensure the trigger is present (will re-bind to the updated function)
DROP TRIGGER IF EXISTS trg_fish_before_insert_code ON public.fish;
CREATE TRIGGER trg_fish_before_insert_code
BEFORE INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.bi_set_fish_code();

COMMIT;

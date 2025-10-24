BEGIN;

-- 1) Unordered uniqueness for conceptual pairs
--    (A,B) == (B,A)
CREATE UNIQUE INDEX IF NOT EXISTS fish_pairs_pair_unique
ON public.fish_pairs (
  LEAST(mom_fish_code, dad_fish_code),
  GREATEST(mom_fish_code, dad_fish_code)
);

-- 2) Canonicalize rows (belt & suspenders)
CREATE OR REPLACE FUNCTION public.fish_pairs_canonicalize()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.mom_fish_code IS NOT NULL AND NEW.dad_fish_code IS NOT NULL THEN
    IF NEW.mom_fish_code > NEW.dad_fish_code THEN
      DECLARE tmp text := NEW.mom_fish_code;
      NEW.mom_fish_code := NEW.dad_fish_code;
      NEW.dad_fish_code := tmp;
    END IF;
  END IF;
  RETURN NEW;
END$$;

DROP TRIGGER IF EXISTS trg_fish_pairs_canonicalize ON public.fish_pairs;
CREATE TRIGGER trg_fish_pairs_canonicalize
BEFORE INSERT OR UPDATE ON public.fish_pairs
FOR EACH ROW EXECUTE FUNCTION public.fish_pairs_canonicalize();

COMMIT;

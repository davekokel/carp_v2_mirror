BEGIN;

-- 1) Add columns on the concept table
ALTER TABLE public.crosses
ADD COLUMN IF NOT EXISTS cross_name text,
ADD COLUMN IF NOT EXISTS cross_nickname text;

-- 2) Helper: best-effort "genotype" string for a fish_code
--    Try fish.genotype, then fish.name, then the fish_code itself
CREATE OR REPLACE FUNCTION public.get_fish_genotype(p_code text)
RETURNS text LANGUAGE sql STABLE AS $$
  SELECT COALESCE(
           (SELECT f.genotype FROM public.fish f WHERE f.fish_code = p_code ORDER BY f.created_at DESC LIMIT 1),
           (SELECT f.name     FROM public.fish f WHERE f.fish_code = p_code ORDER BY f.created_at DESC LIMIT 1),
           p_code
         );
$$;

-- 3) Generator for concept name: "mom_genotype × dad_genotype"
CREATE OR REPLACE FUNCTION public.gen_cross_name(p_mom text, p_dad text)
RETURNS text LANGUAGE sql STABLE AS $$
  SELECT public.get_fish_genotype(p_mom) || ' × ' || public.get_fish_genotype(p_dad);
$$;

-- 4) Trigger: on INSERT, backfill cross_name; set cross_nickname if empty
CREATE OR REPLACE FUNCTION public.trg_cross_name_fill()
RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
  IF NEW.cross_name IS NULL OR btrim(NEW.cross_name) = '' THEN
    NEW.cross_name := public.gen_cross_name(NEW.mother_code, NEW.father_code);
  END IF;
  IF NEW.cross_nickname IS NULL OR btrim(NEW.cross_nickname) = '' THEN
    NEW.cross_nickname := NEW.cross_name;
  END IF;
  RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_cross_name_fill ON public.crosses;
CREATE TRIGGER trg_cross_name_fill
BEFORE INSERT ON public.crosses
FOR EACH ROW EXECUTE FUNCTION public.trg_cross_name_fill();

-- 5) One-off backfill for existing rows
UPDATE public.crosses x
SET
    cross_name = COALESCE(x.cross_name, public.gen_cross_name(x.mother_code, x.father_code)),
    cross_nickname = COALESCE(x.cross_nickname, COALESCE(x.cross_name, public.gen_cross_name(x.mother_code, x.father_code)));

COMMIT;

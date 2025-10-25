BEGIN;

-- 1) Canonical genotype stored on fish_pairs
ALTER TABLE public.fish_pairs
  ADD COLUMN IF NOT EXISTS pair_genotype text;

COMMENT ON COLUMN public.fish_pairs.pair_genotype
  IS 'Canonical conceptual genotype for this fish pair. Used as default for clutches when expected_genotype is NULL.';

-- 2) Normalizer (idempotent, immutable)
CREATE OR REPLACE FUNCTION public._norm_genotype(txt text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT NULLIF(
           btrim(regexp_replace(coalesce($1,'')::text, '\s*;+\s*', '; ', 'g')),
           ''
         )
$$;

-- 3) Backfill pair_genotype from genotype_elems if that column exists and pair_genotype is empty
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='fish_pairs'
      AND column_name='genotype_elems'
  ) THEN
    UPDATE public.fish_pairs
       SET pair_genotype = public._norm_genotype(array_to_string(genotype_elems, '; '))
     WHERE pair_genotype IS NULL
       AND genotype_elems IS NOT NULL;
  END IF;
END$$;

-- 4) Trigger to default clutches.expected_genotype from the pair when NULL
CREATE OR REPLACE FUNCTION public.clutches_default_expected_genotype()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
BEGIN
  IF NEW.expected_genotype IS NULL AND NEW.fish_pair_id IS NOT NULL THEN
    SELECT public._norm_genotype(fp.pair_genotype)
      INTO NEW.expected_genotype
      FROM public.fish_pairs fp
     WHERE fp.fish_pair_id = NEW.fish_pair_id;
  END IF;
  RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_clutches_expected_default ON public.clutches;
CREATE TRIGGER trg_clutches_expected_default
BEFORE INSERT OR UPDATE OF expected_genotype, fish_pair_id
ON public.clutches
FOR EACH ROW
EXECUTE FUNCTION public.clutches_default_expected_genotype();

COMMIT;

BEGIN;

-- BEFORE INSERT/UPDATE: fill modern cols from legacy if modern is missing
CREATE OR REPLACE FUNCTION public.trg_registry_fill_modern()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.transgene_base_code IS NULL THEN
    NEW.transgene_base_code := NEW.base_code;
  END IF;
  IF NEW.allele_nickname IS NULL THEN
    NEW.allele_nickname := NEW.legacy_label;
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_registry_fill_modern ON public.transgene_allele_registry;
CREATE TRIGGER trg_registry_fill_modern
BEFORE INSERT OR UPDATE ON public.transgene_allele_registry
FOR EACH ROW
EXECUTE FUNCTION public.trg_registry_fill_modern();

COMMIT;

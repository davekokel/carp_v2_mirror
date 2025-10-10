BEGIN;

-- trigger function: on insert/update of plasmids, if supports_invitro_rna is true → ensure RNA
CREATE OR REPLACE FUNCTION public.trg_plasmid_auto_ensure_rna()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  -- only when flag is true and we have a code
  IF NEW.supports_invitro_rna IS TRUE AND NEW.code IS NOT NULL AND btrim(NEW.code) <> '' THEN
    -- ensure the RNA with default '-RNA' suffix; name defaults to code||'-RNA' inside helper
    PERFORM (SELECT * FROM public.ensure_rna_for_plasmid(NEW.code, '-RNA', NEW.name, NEW.created_by, NEW.notes));
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_plasmids_auto_ensure_rna ON public.plasmids;

CREATE TRIGGER trg_plasmids_auto_ensure_rna
AFTER INSERT OR UPDATE OF supports_invitro_rna, code
ON public.plasmids
FOR EACH ROW
EXECUTE FUNCTION public.trg_plasmid_auto_ensure_rna();

COMMIT;

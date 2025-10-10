BEGIN;

CREATE OR REPLACE FUNCTION public.trg_plasmid_auto_ensure_rna()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.supports_invitro_rna IS TRUE
     AND NEW.code IS NOT NULL
     AND btrim(NEW.code) <> '' THEN
    -- Call the helper; we don't need its return values here
    PERFORM public.ensure_rna_for_plasmid(NEW.code, '-RNA', NEW.name, NEW.created_by, NEW.notes);
  END IF;
  RETURN NEW;
END;
$$;

-- (Recreate trigger is not necessary; body replacement is enough)
COMMIT;

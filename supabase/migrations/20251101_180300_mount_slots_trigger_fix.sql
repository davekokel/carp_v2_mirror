BEGIN;

CREATE OR REPLACE FUNCTION public.ensure_mount_slots_trg()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM public.ensure_mount_slots(NEW.id);
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_mounts_seed_slots ON public.mounts;

CREATE TRIGGER trg_mounts_seed_slots
AFTER INSERT ON public.mounts
FOR EACH ROW
EXECUTE FUNCTION public.ensure_mount_slots_trg();

COMMIT;

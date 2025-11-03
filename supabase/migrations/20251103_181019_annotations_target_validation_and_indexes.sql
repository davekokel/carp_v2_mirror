BEGIN;

CREATE OR REPLACE FUNCTION public.fn_validate_join_annotations_target()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  ok boolean := false;
  t text := lower(new.target_type);
BEGIN
  IF t = 'clutch' THEN
    SELECT EXISTS(SELECT 1 FROM public.clutches c WHERE c.id=new.target_id) INTO ok;
  ELSIF t = 'mount' THEN
    SELECT EXISTS(SELECT 1 FROM public.mounts m WHERE m.id=new.target_id) INTO ok;
  ELSIF t = 'mount_slot' OR t = 'mountslot' THEN
    SELECT EXISTS(SELECT 1 FROM public.mount_slots s WHERE s.id=new.target_id) INTO ok;
  ELSE
    RAISE EXCEPTION 'join_annotations.target_type must be one of {clutch, mount, mount_slot}; got: %', new.target_type;
  END IF;

  IF NOT ok THEN
    RAISE EXCEPTION 'join_annotations.target_id % does not exist for target_type %', new.target_id, new.target_type;
  END IF;

  new.target_type := CASE
    WHEN t IN ('mount_slot','mountslot') THEN 'mount_slot'
    ELSE t
  END;

  RETURN new;
END
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname='trg_validate_join_annotations_target'
      AND tgrelid='public.join_annotations'::regclass
  ) THEN
    CREATE TRIGGER trg_validate_join_annotations_target
    BEFORE INSERT OR UPDATE OF target_type, target_id
    ON public.join_annotations
    FOR EACH ROW
    EXECUTE FUNCTION public.fn_validate_join_annotations_target();
  END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_join_annotations_target ON public.join_annotations (target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_join_annotations_annotation_id ON public.join_annotations (annotation_id);

COMMIT;

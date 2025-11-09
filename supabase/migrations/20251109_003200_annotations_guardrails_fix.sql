BEGIN;

-- 1) Create the enum type only if it doesn't exist
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'annotation_target_kind') THEN
    CREATE TYPE annotation_target_kind AS ENUM ('fish','clutch_inst','cross','tank','plasmid');
  END IF;
END$$;

-- 2) Add discriminator column if missing
ALTER TABLE public.join_annotations
  ADD COLUMN IF NOT EXISTS target_kind annotation_target_kind;

-- 3) Helpful index for lookups and the trigger
CREATE INDEX IF NOT EXISTS idx_join_annotations_kind_id
  ON public.join_annotations(target_kind, target_id);

-- 4) Deferrable "FK-like" constraint trigger
CREATE OR REPLACE FUNCTION public.enforce_join_annotations_fk()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ok boolean;
BEGIN
  IF NEW.target_id IS NULL OR NEW.target_kind IS NULL THEN
    RAISE EXCEPTION 'join_annotations requires target_kind and target_id';
  END IF;

  CASE NEW.target_kind
    WHEN 'fish'        THEN SELECT EXISTS (SELECT 1 FROM public.fish             p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'clutch_inst' THEN SELECT EXISTS (SELECT 1 FROM public.clutch_instances p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'cross'       THEN SELECT EXISTS (SELECT 1 FROM public.crosses          p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'tank'        THEN SELECT EXISTS (SELECT 1 FROM public.tanks            p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'plasmid'     THEN SELECT EXISTS (SELECT 1 FROM public.plasmids         p WHERE p.id=NEW.target_id) INTO ok;
    ELSE
      RAISE EXCEPTION 'Unknown target_kind: %', NEW.target_kind;
  END CASE;

  IF NOT ok THEN
    RAISE EXCEPTION 'join_annotations % → % does not reference an existing row', NEW.target_kind, NEW.target_id;
  END IF;

  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_enforce_join_annotations_fk ON public.join_annotations;
CREATE CONSTRAINT TRIGGER trg_enforce_join_annotations_fk
AFTER INSERT OR UPDATE ON public.join_annotations
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION public.enforce_join_annotations_fk();

COMMIT;

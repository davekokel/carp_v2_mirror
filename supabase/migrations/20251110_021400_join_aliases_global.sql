BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='alias_target_kind') THEN
    CREATE TYPE alias_target_kind AS ENUM
      ('fluor','tag','dye','rna','plasmid','fish','tank','cross','clutch_inst','treated_clutch');
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS public.join_aliases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target_kind alias_target_kind NOT NULL,
  target_id uuid NOT NULL,
  alias text NOT NULL,
  alias_norm text GENERATED ALWAYS AS (lower(btrim(alias))) STORED,
  created_at timestamptz DEFAULT now(),
  CONSTRAINT uq_alias_per_target UNIQUE (target_kind, target_id, alias_norm)
);
CREATE INDEX IF NOT EXISTS idx_join_aliases_norm ON public.join_aliases(alias_norm);
CREATE INDEX IF NOT EXISTS idx_join_aliases_kind_id ON public.join_aliases(target_kind, target_id);

CREATE OR REPLACE FUNCTION public.enforce_join_aliases_fk()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ok boolean;
BEGIN
  CASE NEW.target_kind
    WHEN 'fluor'          THEN SELECT EXISTS (SELECT 1 FROM public.fluors            p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'tag'            THEN SELECT EXISTS (SELECT 1 FROM public.tags              p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'dye'            THEN SELECT EXISTS (SELECT 1 FROM public.dyes              p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'rna'            THEN SELECT EXISTS (SELECT 1 FROM public.rnas              p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'plasmid'        THEN SELECT EXISTS (SELECT 1 FROM public.plasmids          p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'fish'           THEN SELECT EXISTS (SELECT 1 FROM public.fish              p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'tank'           THEN SELECT EXISTS (SELECT 1 FROM public.tanks             p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'cross'          THEN SELECT EXISTS (SELECT 1 FROM public.crosses           p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'clutch_inst'    THEN SELECT EXISTS (SELECT 1 FROM public.clutch_instances  p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'treated_clutch' THEN SELECT EXISTS (SELECT 1 FROM public.treated_clutches  p WHERE p.id=NEW.target_id) INTO ok;
    ELSE RAISE EXCEPTION 'Unknown target_kind: %', NEW.target_kind;
  END CASE;
  IF NOT ok THEN
    RAISE EXCEPTION 'join_aliases % → % does not reference an existing row', NEW.target_kind, NEW.target_id;
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_enforce_join_aliases_fk ON public.join_aliases;
CREATE CONSTRAINT TRIGGER trg_enforce_join_aliases_fk
AFTER INSERT OR UPDATE ON public.join_aliases
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION public.enforce_join_aliases_fk();

COMMIT;

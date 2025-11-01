BEGIN;

ALTER TABLE public.plasmids
  ADD COLUMN IF NOT EXISTS code                   text,
  ADD COLUMN IF NOT EXISTS name                   text,
  ADD COLUMN IF NOT EXISTS nickname               text,
  ADD COLUMN IF NOT EXISTS resistance             text,
  ADD COLUMN IF NOT EXISTS supports_invitro_rna   boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS notes                  text,
  ADD COLUMN IF NOT EXISTS created_by             text;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid='public.plasmids'::regclass
      AND conname='uq_plasmids_code'
  ) THEN
    ALTER TABLE public.plasmids
      ADD CONSTRAINT uq_plasmids_code UNIQUE (code);
  END IF;
END $$;

COMMIT;

BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_rnas_base_plasmid_code'
      AND conrelid='public.rnas'::regclass
  ) THEN
    ALTER TABLE public.rnas DROP CONSTRAINT fk_rnas_base_plasmid_code;
  END IF;
END$$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='idx_rnas_base_plasmid_code'
  ) THEN
    DROP INDEX public.idx_rnas_base_plasmid_code;
  END IF;
END$$;

COMMIT;

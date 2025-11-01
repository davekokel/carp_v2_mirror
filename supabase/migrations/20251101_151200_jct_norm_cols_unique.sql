BEGIN;

-- Add normalized columns (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='join_clutch_treatments'
      AND column_name='treatment_type_norm'
  ) THEN
    ALTER TABLE public.join_clutch_treatments
      ADD COLUMN treatment_type_norm text
      GENERATED ALWAYS AS ( lower(btrim(coalesce(treatment_type, ''))) ) STORED;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='join_clutch_treatments'
      AND column_name='treatment_code_norm'
  ) THEN
    ALTER TABLE public.join_clutch_treatments
      ADD COLUMN treatment_code_norm text
      GENERATED ALWAYS AS ( lower(btrim(coalesce(treatment_code, ''))) ) STORED;
  END IF;
END $$;

-- Add the deduping unique constraint on normalized columns (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.join_clutch_treatments'::regclass
      AND conname='uq_jct_instance_type_code_norm'
  ) THEN
    ALTER TABLE public.join_clutch_treatments
      ADD CONSTRAINT uq_jct_instance_type_code_norm
      UNIQUE (clutch_instance_id, treatment_type_norm, treatment_code_norm);
  END IF;
END $$;

COMMIT;

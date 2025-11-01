BEGIN;
CREATE TABLE IF NOT EXISTS public.join_clutch_treatments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_instance_id uuid NOT NULL REFERENCES public.clutch_instances(id) ON DELETE CASCADE,
  treatment_type text NOT NULL,
  treatment_code text NOT NULL,
  treatment_name text,
  notes text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now()
);
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='treatment_type_norm'
  ) THEN
    EXECUTE 'ALTER TABLE public.join_clutch_treatments ADD COLUMN treatment_type_norm text GENERATED ALWAYS AS (lower(btrim(coalesce(treatment_type, '''')))) STORED';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='treatment_code_norm'
  ) THEN
    EXECUTE 'ALTER TABLE public.join_clutch_treatments ADD COLUMN treatment_code_norm text GENERATED ALWAYS AS (lower(btrim(coalesce(treatment_code, '''')))) STORED';
  END IF;
END $$;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.join_clutch_treatments'::regclass AND conname='uq_jct_instance_type_code_norm'
  ) THEN
    ALTER TABLE public.join_clutch_treatments
      ADD CONSTRAINT uq_jct_instance_type_code_norm
      UNIQUE (clutch_instance_id, treatment_type_norm, treatment_code_norm);
  END IF;
END $$;
CREATE INDEX IF NOT EXISTS ix_jct_clutch ON public.join_clutch_treatments (clutch_instance_id);
CREATE INDEX IF NOT EXISTS ix_jct_type   ON public.join_clutch_treatments (treatment_type_norm);
CREATE INDEX IF NOT EXISTS ix_jct_code   ON public.join_clutch_treatments (treatment_code_norm);
COMMIT;

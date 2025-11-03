BEGIN;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='join_clutch_treatments'
  ) THEN
    CREATE TABLE public.join_clutch_treatments (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      clutch_instance_id uuid NOT NULL,
      created_by text,
      created_at timestamptz NOT NULL DEFAULT now(),
      treatment_id uuid
    );
  END IF;
END$$;
CREATE INDEX IF NOT EXISTS idx_join_clutch_treatments_clutch_instance_id ON public.join_clutch_treatments (clutch_instance_id);
CREATE INDEX IF NOT EXISTS idx_join_clutch_treatments_treatment_id ON public.join_clutch_treatments (treatment_id);
COMMIT;

BEGIN;

-- Only add the clutch FK (no column drops here — later migrations handle cleanup)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='join_clutch_treatments'
      AND constraint_name='fk_jct_clutch'
  ) THEN
    ALTER TABLE public.join_clutch_treatments
      ADD CONSTRAINT fk_jct_clutch
      FOREIGN KEY (clutch_instance_id) REFERENCES public.clutches(id)
      ON UPDATE CASCADE ON DELETE CASCADE;
  END IF;
END$$;

-- Supporting indexes (safe/idempotent)
CREATE INDEX IF NOT EXISTS idx_jct_clutch
  ON public.join_clutch_treatments (clutch_instance_id);

CREATE INDEX IF NOT EXISTS idx_jct_treatment
  ON public.join_clutch_treatments (treatment_id);

COMMIT;

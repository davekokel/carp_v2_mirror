BEGIN;
CREATE INDEX IF NOT EXISTS idx_join_clutch_treatments_treatment_code ON public.join_clutch_treatments(treatment_code);
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_join_clutch_treatments_treat_code'
      AND conrelid='public.join_clutch_treatments'::regclass
  ) THEN
    ALTER TABLE public.join_clutch_treatments
      ADD CONSTRAINT fk_join_clutch_treatments_treat_code
      FOREIGN KEY (treatment_code) REFERENCES public.treatments(treat_code)
      ON UPDATE RESTRICT ON DELETE RESTRICT
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;
COMMIT;

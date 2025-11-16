BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.join_treatment_dyes'::regclass
      AND conname  = 'fk_jtd_dye'
  ) THEN
    ALTER TABLE public.join_treatment_dyes
      ADD CONSTRAINT fk_jtd_dye
      FOREIGN KEY (dye_id)
      REFERENCES public.dyes(id)
      ON UPDATE CASCADE ON DELETE CASCADE;
  END IF;
END$$;

COMMIT;

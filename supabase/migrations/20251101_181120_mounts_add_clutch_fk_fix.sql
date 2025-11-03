BEGIN;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='mounts' AND constraint_name='fk_mounts_clutch'
  ) THEN
    ALTER TABLE public.mounts
      ADD CONSTRAINT fk_mounts_clutch
      FOREIGN KEY (clutch_instance_id) REFERENCES public.clutches(id)
      ON UPDATE CASCADE ON DELETE SET NULL NOT VALID;
  END IF;
END$$;

DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n
  FROM public.mounts m
  LEFT JOIN public.clutches c ON c.id = m.clutch_instance_id
  WHERE m.clutch_instance_id IS NOT NULL AND c.id IS NULL;

  IF n = 0 THEN
    BEGIN
      ALTER TABLE public.mounts VALIDATE CONSTRAINT fk_mounts_clutch;
    EXCEPTION WHEN undefined_object THEN
      NULL;
    END;
  END IF;
END$$;

CREATE INDEX IF NOT EXISTS ix_mounts_clutch_instance_id ON public.mounts(clutch_instance_id);
COMMIT;

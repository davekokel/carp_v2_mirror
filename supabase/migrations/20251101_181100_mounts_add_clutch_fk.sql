BEGIN;
ALTER TABLE public.mounts ADD COLUMN IF NOT EXISTS clutch_instance_id uuid;
CREATE INDEX IF NOT EXISTS ix_mounts_clutch ON public.mounts(clutch_instance_id);
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'mounts_clutch_fk'
      AND conrelid = 'public.mounts'::regclass
  ) THEN
    EXECUTE 'ALTER TABLE public.mounts
             ADD CONSTRAINT mounts_clutch_fk
             FOREIGN KEY (clutch_instance_id) REFERENCES public.clutch_instances(id)
             ON UPDATE CASCADE ON DELETE SET NULL';
  END IF;
END $$;
COMMIT;

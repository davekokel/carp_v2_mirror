BEGIN;

-- Drop any foreign key from imaging_slots that points to fish_instance(id)
DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT conname
    FROM pg_constraint
    WHERE conrelid = 'public.imaging_slots'::regclass
      AND contype = 'f'
      AND confrelid = 'public.fish_instance'::regclass
  LOOP
    EXECUTE format('ALTER TABLE public.imaging_slots DROP CONSTRAINT %I', r.conname);
  END LOOP;
END $$;

COMMIT;

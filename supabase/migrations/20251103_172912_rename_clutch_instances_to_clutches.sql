BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='clutches'
  ) THEN
    EXECUTE 'ALTER TABLE public.clutches RENAME TO clutches_legacy';
  END IF;
END $$;

ALTER TABLE public.clutch_instances RENAME TO clutches;

DROP VIEW IF EXISTS public.v_clutch_instances;
CREATE VIEW public.v_clutch_instances AS
SELECT * FROM public.clutches;

COMMIT;

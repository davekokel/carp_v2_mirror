-- 1) Drop any DEFAULT that invokes gen_clutch_instance_code() (or any default) on clutch_instance_code
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='clutch_instances'
      AND column_name='clutch_instance_code'
      AND column_default IS NOT NULL
  ) THEN
    EXECUTE 'ALTER TABLE public.clutch_instances ALTER COLUMN clutch_instance_code DROP DEFAULT';
  END IF;
END $$;

-- 2) Create a trigger that sets clutch_instance_code after the "ensure cross" trigger has aligned the cross
CREATE OR REPLACE FUNCTION public.trg_clutch_set_code_from_fn()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  -- Only set if still NULL; relies on ensure trigger to have validated / filled cross
  IF NEW.clutch_instance_code IS NULL THEN
    NEW.clutch_instance_code := gen_clutch_instance_code();
  END IF;
  RETURN NEW;
END
$$;

-- 3) Drop any old code trigger we created and re-create it with a late-sorting name so it runs after ensure
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_trigger
    WHERE tgrelid='public.clutch_instances'::regclass
      AND NOT tgisinternal
      AND tgname = 'zz_clutch_set_code'
  ) THEN
    EXECUTE 'DROP TRIGGER zz_clutch_set_code ON public.clutch_instances';
  END IF;

  -- Ensure our ensure-first trigger exists (we don't overwrite it here)
  -- Create code trigger that runs AFTER the aa_* ensure trigger due to name ordering
  EXECUTE 'CREATE TRIGGER zz_clutch_set_code
           BEFORE INSERT ON public.clutch_instances
           FOR EACH ROW
           EXECUTE FUNCTION public.trg_clutch_set_code_from_fn()';
END $$;

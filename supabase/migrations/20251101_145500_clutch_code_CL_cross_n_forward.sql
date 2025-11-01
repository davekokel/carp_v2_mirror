BEGIN;

-- Per-cross counter store (one row per cross)
CREATE TABLE IF NOT EXISTS public.cross_clutch_counters (
  cross_id  uuid PRIMARY KEY REFERENCES public.crosses(id) ON DELETE CASCADE,
  next_num  integer NOT NULL DEFAULT 1
);

-- Atomically get the next ordinal for a given cross (1,2,3,...) without gaps on concurrent inserts
CREATE OR REPLACE FUNCTION public.next_clutch_ordinal(p_cross_id uuid)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
  assigned integer;
BEGIN
  -- 1) try to bump existing row and return the previous value
  UPDATE public.cross_clutch_counters
     SET next_num = next_num + 1
   WHERE cross_id = p_cross_id
   RETURNING next_num - 1 INTO assigned;

  IF assigned IS NOT NULL THEN
    RETURN assigned;
  END IF;

  -- 2) first time for this cross_id → insert seed row with next_num=2 and assign 1
  LOOP
    BEGIN
      INSERT INTO public.cross_clutch_counters(cross_id, next_num)
      VALUES (p_cross_id, 2);   -- next insert will see 2; we assign 1 now
      RETURN 1;
    EXCEPTION WHEN unique_violation THEN
      -- someone inserted concurrently; loop back to UPDATE path
      UPDATE public.cross_clutch_counters
         SET next_num = next_num + 1
       WHERE cross_id = p_cross_id
       RETURNING next_num - 1 INTO assigned;
      IF assigned IS NOT NULL THEN
        RETURN assigned;
      END IF;
    END;
  END LOOP;
END
$$;

-- Build the final code using the cross's run code
CREATE OR REPLACE FUNCTION public.gen_clutch_instance_code(p_cross_id uuid)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
  run_code text;
  ord integer;
BEGIN
  SELECT cr.cross_run_code INTO run_code
  FROM public.crosses cr
  WHERE cr.id = p_cross_id;

  IF run_code IS NULL OR btrim(run_code) = '' THEN
    -- If a cross code hasn't been minted yet, keep a safe placeholder
    run_code := 'CR-UNKNOWN';
  END IF;

  ord := public.next_clutch_ordinal(p_cross_id);
  RETURN 'CL(' || run_code || ')-' || ord::text;
END
$$;

-- Forward-only trigger: set code if missing on INSERTs
CREATE OR REPLACE FUNCTION public.trg_clutch_code_CL_cross_n()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.clutch_instance_code IS NULL OR btrim(NEW.clutch_instance_code) = '' THEN
    IF NEW.cross_instance_id IS NULL THEN
      RAISE EXCEPTION 'Cannot generate clutch code without cross_instance_id';
    END IF;
    NEW.clutch_instance_code := public.gen_clutch_instance_code(NEW.cross_instance_id);
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_clutch_code_CL_cross_n ON public.clutch_instances;
CREATE TRIGGER trg_clutch_code_CL_cross_n
BEFORE INSERT ON public.clutch_instances
FOR EACH ROW
EXECUTE FUNCTION public.trg_clutch_code_CL_cross_n();

-- Ensure codes are unique going forward (does not backfill)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.clutch_instances'::regclass
      AND conname='uq_clutch_instance_code'
  ) THEN
    ALTER TABLE public.clutch_instances
      ADD CONSTRAINT uq_clutch_instance_code UNIQUE (clutch_instance_code);
  END IF;
END $$;

COMMIT;

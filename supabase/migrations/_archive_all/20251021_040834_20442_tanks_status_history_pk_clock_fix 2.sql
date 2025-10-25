SET search_path=public,public;

-- 1) Ensure table exists (noop if already there)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='tank_status_history') THEN
    CREATE TABLE public.tank_status_history (
      tank_id bigint NOT NULL REFERENCES public.tanks(tank_id) ON DELETE CASCADE,
      status public.tank_status NOT NULL,
      reason text,
      changed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      changed_by uuid DEFAULT auth.uid()
    );
  END IF;
END $$;

-- 2) Add a surrogate PK and index, replace any old PK on (tank_id, changed_at)
DO $$
DECLARE
  pk_name text;
  has_tsh_id boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_status_history' AND column_name='tsh_id'
  ) INTO has_tsh_id;

  IF NOT has_tsh_id THEN
    ALTER TABLE public.tank_status_history ADD COLUMN tsh_id bigserial;
  END IF;

  SELECT c.conname
  INTO pk_name
  FROM pg_constraint c
  JOIN pg_class t ON t.oid=c.conrelid
  JOIN pg_namespace n ON n.oid=t.relnamespace
  WHERE c.contype='p' AND n.nspname='public' AND t.relname='tank_status_history';

  IF pk_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE public.tank_status_history DROP CONSTRAINT %I', pk_name);
  END IF;

  -- Set new PK on the surrogate key
  ALTER TABLE public.tank_status_history
    ADD CONSTRAINT tank_status_history_pkey PRIMARY KEY (tsh_id);

  -- Helpful ordering index (if it doesn't exist already)
  IF NOT EXISTS (
    SELECT 1 FROM pg_class i
    JOIN pg_namespace ns ON ns.oid=i.relnamespace
    WHERE ns.nspname='public' AND i.relname='ix_tsh_tank_id_changed_at'
  ) THEN
    CREATE INDEX ix_tsh_tank_id_changed_at ON public.tank_status_history(tank_id, changed_at DESC);
  END IF;

  -- Ensure changed_at defaults to wall clock (not tx time)
  ALTER TABLE public.tank_status_history
    ALTER COLUMN changed_at SET DEFAULT clock_timestamp();
END $$;

-- 3) Rewrite helper to stamp wall-clock time (extra safety)
CREATE OR REPLACE FUNCTION public._tank_set_status(p_tank_id bigint, p_status public.tank_status, p_reason text)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO public.tank_status_history (tank_id, status, reason, changed_at)
  VALUES (p_tank_id, p_status, p_reason, clock_timestamp());
END
$$;

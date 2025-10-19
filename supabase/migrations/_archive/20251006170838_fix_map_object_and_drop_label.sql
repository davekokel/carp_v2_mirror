BEGIN;

-- If fish_seed_batches_map is a VIEW, drop it and replace with a TABLE
DO $$
DECLARE
  obj_kind text;
BEGIN
  SELECT CASE c.relkind
           WHEN 'r' THEN 'table'
           WHEN 'v' THEN 'view'
           WHEN 'm' THEN 'matview'
           WHEN 'p' THEN 'partitioned_table'
           ELSE c.relkind::text
         END
    INTO obj_kind
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND c.relname = 'fish_seed_batches_map'
  LIMIT 1;

  IF obj_kind = 'view' OR obj_kind = 'matview' THEN
    EXECUTE 'DROP VIEW IF EXISTS public.fish_seed_batches_map CASCADE';
  END IF;
END$$;

-- Create the TABLE (idempotent)
CREATE TABLE IF NOT EXISTS public.fish_seed_batches_map (
    fish_id uuid NOT NULL REFERENCES public.fish (id_uuid) ON DELETE CASCADE,
    seed_batch_id text NULL,
    logged_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fsbm_fish_id ON public.fish_seed_batches_map (fish_id);
CREATE INDEX IF NOT EXISTS idx_fsbm_seed_batch_id ON public.fish_seed_batches_map (seed_batch_id);

-- Now drop batch_label if a legacy table still has it
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish_seed_batches_map'
      AND column_name='batch_label'
  ) THEN
    ALTER TABLE public.fish_seed_batches_map DROP COLUMN batch_label;
  END IF;
END$$;

COMMIT;

BEGIN;

CREATE TABLE IF NOT EXISTS public.fish_seed_batches_map (
  fish_id       uuid        NOT NULL REFERENCES public.fish(id_uuid) ON DELETE CASCADE,
  seed_batch_id text        NULL,
  logged_at     timestamptz NOT NULL DEFAULT now(),
  created_at    timestamptz NOT NULL DEFAULT now()
);
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

CREATE INDEX IF NOT EXISTS idx_fsbm_fish_id       ON public.fish_seed_batches_map(fish_id);
CREATE INDEX IF NOT EXISTS idx_fsbm_seed_batch_id ON public.fish_seed_batches_map(seed_batch_id);


COMMIT;

BEGIN;

CREATE TABLE IF NOT EXISTS public.fish_seed_batches_map (
  fish_id uuid NOT NULL,
  seed_batch_id text        NULL,
  batch_label   text        NULL,
  logged_at     timestamptz NOT NULL DEFAULT now(),
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fsbm_fish_id       ON public.fish_seed_batches_map(fish_id);
CREATE INDEX IF NOT EXISTS idx_fsbm_seed_batch_id ON public.fish_seed_batches_map(seed_batch_id);

COMMIT;

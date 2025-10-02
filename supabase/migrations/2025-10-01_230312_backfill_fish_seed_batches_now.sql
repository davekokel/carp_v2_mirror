INSERT INTO public.fish_seed_batches (fish_id, seed_batch_id, updated_at)
SELECT DISTINCT ON (f.id_uuid)
  f.id_uuid,
  llf.seed_batch_id,
  now()
FROM public.load_log_fish llf
JOIN public.fish f ON f.id_uuid = llf.fish_id
WHERE llf.seed_batch_id IS NOT NULL
ORDER BY f.id_uuid, llf.logged_at DESC
ON CONFLICT (fish_id) DO UPDATE
  SET seed_batch_id = EXCLUDED.seed_batch_id,
      updated_at    = EXCLUDED.updated_at;

CREATE TABLE IF NOT EXISTS public.seed_batches(
  seed_batch_id text PRIMARY KEY,
  batch_label   text,
  created_at    timestamptz DEFAULT now()
);

INSERT INTO public.seed_batches(seed_batch_id, batch_label)
SELECT DISTINCT seed_batch_id, seed_batch_id
FROM public.fish_seed_batches
WHERE seed_batch_id IS NOT NULL
ON CONFLICT (seed_batch_id) DO NOTHING;

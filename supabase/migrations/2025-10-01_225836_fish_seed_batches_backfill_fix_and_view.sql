-- Backfill only for fish that actually exist
INSERT INTO public.fish_seed_batches (fish_id, seed_batch_id)
SELECT DISTINCT ON (f.id_uuid)
  f.id_uuid,
  llf.seed_batch_id
FROM public.load_log_fish llf
JOIN public.fish f ON f.id_uuid = llf.fish_id   -- <-- only rows that have a real fish
WHERE llf.seed_batch_id IS NOT NULL
ORDER BY f.id_uuid, llf.logged_at DESC
ON CONFLICT (fish_id) DO UPDATE
  SET seed_batch_id = EXCLUDED.seed_batch_id,
      updated_at    = now();

-- Robust labeled overview:
-- vw_fish_overview → fish → fish_seed_batches → optional pretty label
CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
WITH seed_map AS (
  SELECT
    TRIM(f.fish_code) AS fish_code_norm,
    fsb.seed_batch_id
  FROM public.fish f
  JOIN public.fish_seed_batches fsb
    ON fsb.fish_id = f.id_uuid
),
label_map AS (
  SELECT seed_batch_id, NULLIF(TRIM(batch_label), '') AS batch_label
  FROM public.seed_batches
)
SELECT
  v.*,
  COALESCE(lm.batch_label, sm.seed_batch_id) AS batch_label
FROM public.vw_fish_overview v
LEFT JOIN seed_map sm
  ON TRIM(v.fish_code) = sm.fish_code_norm
LEFT JOIN label_map lm USING (seed_batch_id);

CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
WITH seed_map AS (
  SELECT DISTINCT ON (fish_code)
    fish_code,
    seed_batch_id
  FROM public.load_log_fish
  WHERE table_name = 'fish' AND action = 'insert' AND seed_batch_id IS NOT NULL
  ORDER BY fish_code, logged_at DESC
),
label_map AS (
  SELECT seed_batch_id, NULLIF(TRIM(batch_label), '') AS batch_label
  FROM public.seed_batches
)
SELECT
  v.*,
  COALESCE(lm.batch_label, sm.seed_batch_id) AS batch_label
FROM public.vw_fish_overview v
LEFT JOIN seed_map sm USING (fish_code)
LEFT JOIN label_map lm USING (seed_batch_id);

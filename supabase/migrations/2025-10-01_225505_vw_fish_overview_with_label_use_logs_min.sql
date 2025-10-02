CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
WITH seed_map AS (
  SELECT DISTINCT ON (f.fish_code)
    f.fish_code,
    llf.seed_batch_id
  FROM public.load_log_fish llf
  JOIN public.fish f ON f.id_uuid = llf.fish_id
  WHERE llf.seed_batch_id IS NOT NULL
  ORDER BY f.fish_code, llf.logged_at DESC
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

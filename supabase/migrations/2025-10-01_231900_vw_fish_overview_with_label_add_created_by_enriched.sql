CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
SELECT
  v.*,
  COALESCE(sb.batch_label, fsb.seed_batch_id)                               AS batch_label,
  COALESCE(NULLIF(TRIM(v.created_by),''), NULLIF(TRIM(f.created_by),''))    AS created_by_enriched
FROM public.vw_fish_overview v
LEFT JOIN public.fish f
  ON UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code))
LEFT JOIN public.fish_seed_batches fsb
  ON fsb.fish_id = f.id_uuid
LEFT JOIN public.seed_batches sb
  ON sb.seed_batch_id = fsb.seed_batch_id;

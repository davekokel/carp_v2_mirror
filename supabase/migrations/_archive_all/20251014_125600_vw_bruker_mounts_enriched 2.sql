CREATE OR REPLACE VIEW public.vw_bruker_mounts_enriched AS
SELECT
  bm.mount_code,
  -- prefer selection_id if present; fall back to id when available
  COALESCE(bm.selection_id::text, bm.id::text) AS selection_id,
  bm.mount_date,
  /* If your table has these columns, you can swap NULLs for real columns later */
  NULL::time                      AS mount_time,
  NULL::int                       AS n_top,
  NULL::int                       AS n_bottom,
  NULL::text                      AS orientation,
  bm.created_at,
  bm.created_by
FROM public.bruker_mounts bm;

DO $$
BEGIN
  IF to_regclass('public.seed_batches') IS NOT NULL THEN
    EXECUTE $v$
      CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
      SELECT
        v.*,
        COALESCE(NULLIF(TRIM(sb.batch_label), ''), v.seed_batch_id) AS batch_label
      FROM public.vw_fish_overview v
      LEFT JOIN public.seed_batches sb USING (seed_batch_id)
    $v$;
  ELSE
    EXECUTE $v$
      CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
      SELECT
        v.*,
        v.seed_batch_id AS batch_label
      FROM public.vw_fish_overview v
    $v$;
  END IF;
END$$;

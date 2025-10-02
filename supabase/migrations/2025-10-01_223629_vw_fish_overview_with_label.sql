DO $$
DECLARE
  has_seed_batch_id boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'vw_fish_overview'
      AND column_name  = 'seed_batch_id'
  ) INTO has_seed_batch_id;

  IF has_seed_batch_id THEN
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
  ELSE
    -- fallback: create the view with a batch_label column present but empty
    EXECUTE $v$
      CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
      SELECT
        v.*,
        NULL::text AS batch_label
      FROM public.vw_fish_overview v
    $v$;
  END IF;
END$$;

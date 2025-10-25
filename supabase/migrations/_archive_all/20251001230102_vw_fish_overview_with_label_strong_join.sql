-- Baseline-safe labeled overview: uses fish_seed_batches if present; no dependency on seed_batches table.
DO $$
BEGIN
  IF to_regclass('public.v_fish_overview') IS NULL THEN
    RAISE NOTICE 'Skip: v_fish_overview missing';
    RETURN;
  END IF;

  -- Drop first to avoid replace/column-shape errors
  EXECUTE 'DROP VIEW IF EXISTS public.v_fish_overview_with_label CASCADE';

  -- If mapping table is present, use it; otherwise just project a NULL label
  IF to_regclass('public.fish_seed_batches') IS NOT NULL THEN
    EXECUTE '
      CREATE VIEW public.v_fish_overview_with_label AS
      SELECT
        v.*,
        fsb.seed_batch_id AS batch_label
      FROM public.v_fish_overview v
      LEFT JOIN public.fish_seed_batches fsb
        ON fsb.fish_id = v.id
    ';
  ELSE
    EXECUTE '
      CREATE VIEW public.v_fish_overview_with_label AS
      SELECT
        v.*,
        NULL::text AS batch_label
      FROM public.v_fish_overview v
    ';
  END IF;
END
$$;

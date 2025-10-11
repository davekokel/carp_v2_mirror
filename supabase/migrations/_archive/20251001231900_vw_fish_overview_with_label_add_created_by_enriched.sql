DO $$
BEGIN
  IF to_regclass('public.v_fish_overview') IS NULL THEN
    RAISE NOTICE 'Skip: v_fish_overview missing';
    RETURN;
  END IF;

  EXECUTE 'DROP VIEW IF EXISTS public.vw_fish_overview_with_label CASCADE';

  IF to_regclass('public.fish') IS NOT NULL AND to_regclass('public.fish_seed_batches') IS NOT NULL THEN
    EXECUTE '
      CREATE VIEW public.vw_fish_overview_with_label AS
      SELECT
        v.*,
        fsb.seed_batch_id AS batch_label,
        COALESCE(NULLIF(BTRIM(v.created_by), ''''),
                 NULLIF(BTRIM(f.created_by), '''')) AS created_by_enriched
      FROM public.v_fish_overview v
      LEFT JOIN public.fish f
        ON f.id = v.id
      LEFT JOIN public.fish_seed_batches fsb
        ON fsb.fish_id = v.id
    ';
  ELSIF to_regclass('public.fish') IS NOT NULL THEN
    EXECUTE '
      CREATE VIEW public.vw_fish_overview_with_label AS
      SELECT
        v.*,
        NULL::text AS batch_label,
        COALESCE(NULLIF(BTRIM(v.created_by), ''''),
                 NULLIF(BTRIM(f.created_by), '''')) AS created_by_enriched
      FROM public.v_fish_overview v
      LEFT JOIN public.fish f
        ON f.id = v.id
    ';
  ELSE
    EXECUTE '
      CREATE VIEW public.vw_fish_overview_with_label AS
      SELECT
        v.*,
        NULL::text AS batch_label,
        NULL::text AS created_by_enriched
      FROM public.v_fish_overview v
    ';
  END IF;
END
$$;

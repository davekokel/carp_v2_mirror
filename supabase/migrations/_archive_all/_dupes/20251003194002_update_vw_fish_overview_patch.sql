DO $$
BEGIN
  IF to_regclass('public.v_fish_overview') IS NULL THEN
    RAISE NOTICE 'Skip: v_fish_overview missing';
    RETURN;
  END IF;

  EXECUTE 'DROP VIEW IF EXISTS public.v_fish_overview_with_label CASCADE';

  IF to_regclass('public.load_log_fish') IS NULL THEN
    EXECUTE 'CREATE VIEW public.v_fish_overview_with_label AS SELECT v.*, NULL::text AS seed_batch_id FROM public.v_fish_overview v';
  ELSE
    EXECUTE $V$
      CREATE VIEW public.v_fish_overview_with_label AS
      SELECT
        v.*, sm.seed_batch_id
      FROM public.v_fish_overview v
      LEFT JOIN (
        SELECT DISTINCT ON (fish_code) fish_code, seed_batch_id
        FROM public.load_log_fish
        WHERE fish_code IS NOT NULL
        ORDER BY fish_code, logged_at DESC
      ) sm ON sm.fish_code = v.fish_code
    $V$;
  END IF;
END
$$;

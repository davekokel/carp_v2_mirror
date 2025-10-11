DO $$
BEGIN
  IF to_regclass('public.v_fish_overview') IS NULL THEN
    RAISE NOTICE 'Skip: v_fish_overview missing';
    RETURN;
  END IF;

  EXECUTE 'DROP VIEW IF EXISTS public.vw_fish_overview_with_label CASCADE';

  IF to_regclass('public.load_log_fish') IS NULL THEN
    EXECUTE $V$
      CREATE VIEW public.vw_fish_overview_with_label AS
      SELECT v.*, NULL::text AS seed_batch_id
      FROM public.v_fish_overview v
    $V$;
  ELSE
    EXECUTE $V$
      CREATE VIEW public.vw_fish_overview_with_label AS
      WITH seed_map AS (
        SELECT DISTINCT ON (llf.fish_code)
          llf.fish_code, llf.seed_batch_id
        FROM public.load_log_fish llf
        WHERE llf.fish_code IS NOT NULL
        ORDER BY llf.fish_code, llf.logged_at DESC
      )
      SELECT
        v.id, v.fish_code, v.name,
        v.transgene_base_code_filled, v.allele_code_filled, v.allele_name_filled,
        v.created_at, v.created_by,
        sm.seed_batch_id
      FROM public.v_fish_overview v
      LEFT JOIN seed_map sm ON sm.fish_code = v.fish_code
    $V$;
  END IF;
END
$$;

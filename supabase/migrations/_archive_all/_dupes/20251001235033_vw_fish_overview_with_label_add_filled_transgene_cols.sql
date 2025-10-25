-- Baseline-safe labeled overview with first-allele helpers.
-- No dependency on seed_batches; no id_uuid; drop-then-create to avoid shape errors.
DO $$
BEGIN
  IF to_regclass('public.v_fish_overview') IS NULL THEN
    RAISE NOTICE 'Skip: v_fish_overview missing';
    RETURN;
  END IF;

  EXECUTE 'DROP VIEW IF EXISTS public.v_fish_overview_with_label CASCADE';

  -- Aggregate genotype from fish_transgene_alleles; extract "first" helpers
  EXECUTE $V$
    CREATE VIEW public.v_fish_overview_with_label AS
    WITH tg AS (
      SELECT
        fta.fish_id,
        ARRAY_REMOVE(ARRAY_AGG(fta.transgene_base_code ORDER BY fta.allele_number NULLS LAST), NULL) AS bases,
        ARRAY_REMOVE(ARRAY_AGG(fta.allele_number       ORDER BY fta.allele_number NULLS LAST), NULL) AS allele_nums
      FROM public.fish_transgene_alleles fta
      GROUP BY fta.fish_id
    ),
    tg_first AS (
      SELECT
        fish_id,
        CASE WHEN array_length(bases,1)       > 0 THEN bases[1]       END AS tg_base_first,
        CASE WHEN array_length(allele_nums,1) > 0 THEN allele_nums[1] END AS allele_num_first,
        NULL::text AS tg_name_first
      FROM tg
    )
    SELECT
      v.*,                                  -- baseline columns from v_fish_overview
      fsb.seed_batch_id AS batch_label,     -- if mapping exists, else NULL
      COALESCE(NULLIF(BTRIM(v.created_by),''), NULLIF(BTRIM(f.created_by),'')) AS created_by_enriched,
      tf.tg_base_first,
      tf.allele_num_first,
      tf.tg_name_first
    FROM public.v_fish_overview v
    LEFT JOIN public.fish f
      ON f.id = v.id
    LEFT JOIN public.fish_seed_batches fsb
      ON fsb.fish_id = v.id
    LEFT JOIN tg_first tf
      ON tf.fish_id = v.id
  $V$;
END
$$;

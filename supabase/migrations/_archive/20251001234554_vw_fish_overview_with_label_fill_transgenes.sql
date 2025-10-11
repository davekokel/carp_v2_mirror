-- Baseline-safe: no transgenes table, no id_uuid; fixes allele_nums[1] typo;
-- drop-then-create to avoid "cannot drop columns from view".

DO $$
BEGIN
  IF to_regclass('public.v_fish_overview') IS NULL THEN
    RAISE NOTICE 'Skip: v_fish_overview missing';
    RETURN;
  END IF;

  EXECUTE 'DROP VIEW IF EXISTS public.vw_fish_overview_with_label CASCADE';

  -- Build label-friendly overview with simple genotype aggregation and first-allele hints
  EXECUTE $V$
    CREATE VIEW public.vw_fish_overview_with_label AS
    WITH tg AS (
      SELECT
        fta.fish_id,
        ARRAY_REMOVE(ARRAY_AGG(fta.transgene_base_code ORDER BY fta.allele_number NULLS LAST), NULL) AS bases,
        ARRAY_REMOVE(ARRAY_AGG(fta.allele_number       ORDER BY fta.allele_number NULLS LAST), NULL) AS allele_nums,
        string_agg(
          fta.transgene_base_code || ':' || fta.allele_number
          || CASE WHEN coalesce(nullif(fta.zygosity,''),'') <> '' THEN ' ('||fta.zygosity||')' ELSE '' END,
          ', ' ORDER BY fta.transgene_base_code, fta.allele_number
        ) AS genotype_text
      FROM public.fish_transgene_alleles fta
      GROUP BY fta.fish_id
    ),
    tg_first AS (
      SELECT
        fish_id,
        CASE WHEN array_length(bases,1)       > 0 THEN bases[1]        END AS tg_base_first,
        CASE WHEN array_length(allele_nums,1) > 0 THEN allele_nums[1]  END AS allele_num_first
      FROM tg
    )
    SELECT
      v.*,
      tf.tg_base_first,
      tf.allele_num_first,
      tg.genotype_text,
      NULL::text AS batch_label,            -- labels are handled by later guarded views if available
      v.created_by AS created_by_enriched   -- simple enrichment; later views may override
    FROM public.v_fish_overview v
    LEFT JOIN tg       ON tg.fish_id = v.id
    LEFT JOIN tg_first tf ON tf.fish_id = v.id
  $V$;
END
$$;

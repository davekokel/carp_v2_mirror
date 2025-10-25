DO $$
BEGIN
  IF to_regclass('public.v_fish_overview') IS NULL THEN
    RAISE NOTICE 'Skip: v_fish_overview missing';
    RETURN;
  END IF;

  -- Drop first to avoid replace/shape issues
  EXECUTE 'DROP VIEW IF EXISTS public.v_fish_overview_with_label CASCADE';

  -- Build a label-friendly overview using only baseline-safe tables
  EXECUTE $V$
    CREATE VIEW public.v_fish_overview_with_label AS
    WITH tg AS (
      SELECT
        fta.fish_id,
        string_agg(
          fta.transgene_base_code || ':' || fta.allele_number
          || CASE WHEN coalesce(nullif(fta.zygosity,''),'') <> '' THEN ' ('||fta.zygosity||')' ELSE '' END,
          ', ' ORDER BY fta.transgene_base_code, fta.allele_number
        ) AS genotype_text
      FROM public.fish_transgene_alleles fta
      GROUP BY fta.fish_id
    )
    SELECT
      v.*,
      tg.genotype_text,
      NULL::text AS batch_label,            -- labels handled in later guarded views if available
      v.created_by AS created_by_enriched   -- prefer v.created_by; later patches may enrich
    FROM public.v_fish_overview v
    LEFT JOIN tg ON tg.fish_id = v.id
  $V$;
END
$$;

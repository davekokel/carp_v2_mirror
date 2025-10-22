-- Baseline-safe labeled overview (no seed_batches join, no id_uuid, no non-baseline columns).
DO $$
BEGIN
  IF to_regclass('public.v_fish_overview') IS NULL THEN
    RAISE NOTICE 'Skip: v_fish_overview missing';
    RETURN;
  END IF;

  -- Drop first to avoid "cannot drop columns from view" errors
  EXECUTE 'DROP VIEW IF EXISTS public.v_fish_overview_with_label CASCADE';

  -- Use only baseline columns from v_fish_overview; add batch_label from fish_seed_batches if present
  CREATE VIEW public.v_fish_overview_with_label AS
  SELECT
    v.id,
    v.fish_code,
    v.name,
    v.transgene_base_code_filled,
    v.allele_code_filled,
    v.allele_name_filled,
    v.created_at,
    v.created_by,
    fsb.seed_batch_id AS batch_label,
    COALESCE(NULLIF(BTRIM(v.created_by),''), NULLIF(BTRIM(f.created_by),'')) AS created_by_enriched
  FROM public.v_fish_overview v
  LEFT JOIN public.fish f
    ON f.id = v.id
  LEFT JOIN public.fish_seed_batches fsb
    ON fsb.fish_id = v.id;
END
$$;

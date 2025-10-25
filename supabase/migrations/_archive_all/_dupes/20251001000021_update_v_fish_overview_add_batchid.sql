DO $$
BEGIN
  -- Only proceed if the baseline table exists.
  IF to_regclass('public.fish') IS NULL THEN
    RAISE NOTICE 'Skipping v_fish_overview rebuild: public.fish missing';
    RETURN;
  END IF;

  -- Rebuild v_fish_overview using ONLY baseline-safe objects.
  -- Keep the same 8-column shape we standardized on so later REPLACEs don't "drop columns".
  EXECUTE $V$
    CREATE OR REPLACE VIEW public.v_fish_overview
    (id, fish_code, name, transgene_base_code_filled, allele_code_filled, allele_name_filled, created_at, created_by) AS
    SELECT
      f.id,
      f.fish_code,
      f.name,
      (
        SELECT array_to_string(array_agg(x.base), ', ')
        FROM (
          SELECT DISTINCT t.transgene_base_code AS base
          FROM public.fish_transgene_alleles t
          WHERE t.fish_id = f.id
          ORDER BY 1
        ) x
      ) AS transgene_base_code_filled,
      (
        SELECT array_to_string(array_agg(x.an), ', ')
        FROM (
          SELECT DISTINCT (t.allele_number::text) AS an
          FROM public.fish_transgene_alleles t
          WHERE t.fish_id = f.id
          ORDER BY 1
        ) x
      ) AS allele_code_filled,
      NULL::text AS allele_name_filled,
      f.created_at,
      f.created_by
    FROM public.fish f;
  $V$;
END
$$;

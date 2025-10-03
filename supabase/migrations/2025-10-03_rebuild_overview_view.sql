DO $$
BEGIN
  -- Drop old definition if present (so we can change column list/order)
  IF to_regclass('public.vw_fish_overview_with_label') IS NOT NULL THEN
    EXECUTE 'DROP VIEW public.vw_fish_overview_with_label';
  END IF;

  IF to_regclass('public.fish_transgene_alleles') IS NOT NULL THEN
    -- Enriched version: every fish + aggregated transgenes if available
    EXECUTE $V$
      CREATE VIEW public.vw_fish_overview_with_label AS
      SELECT
        f.id_uuid,
        f.fish_code,
        f.name::text AS fish_name,
        NULL::text   AS nickname,
        NULL::text   AS line_building_stage,
        NULL::text   AS transgene_pretty_filled,
        -- base codes: distinct + order via subquery
        (
          SELECT array_to_string(array_agg(x.base_code), ', ')
          FROM (
            SELECT DISTINCT t.transgene_base_code AS base_code
            FROM public.fish_transgene_alleles t
            WHERE t.fish_id = f.id_uuid
            ORDER BY t.transgene_base_code
          ) x
        ) AS transgene_base_code_filled,
        -- allele numbers (as text): distinct + order via subquery
        (
          SELECT array_to_string(array_agg(x.allele_text), ', ')
          FROM (
            SELECT DISTINCT (t.allele_number::text) AS allele_text
            FROM public.fish_transgene_alleles t
            WHERE t.fish_id = f.id_uuid
            ORDER BY (t.allele_number::text)
          ) x
        ) AS allele_code_filled,
        NULL::text   AS allele_name_filled,
        f.created_at,
        f.created_by
      FROM public.fish f;
    $V$;
  ELSE
    -- Minimal version: always include every fish; keep expected columns
    EXECUTE $V$
      CREATE VIEW public.vw_fish_overview_with_label AS
      SELECT
        f.id_uuid,
        f.fish_code,
        f.name::text AS fish_name,
        NULL::text   AS nickname,
        NULL::text   AS line_building_stage,
        NULL::text   AS transgene_pretty_filled,
        NULL::text   AS transgene_base_code_filled,
        NULL::text   AS allele_code_filled,
        NULL::text   AS allele_name_filled,
        f.created_at,
        f.created_by
      FROM public.fish f;
    $V$;
  END IF;
END
$$;

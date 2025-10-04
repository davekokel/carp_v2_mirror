DO $$
BEGIN
  -- Always drop first to avoid column-shape replace errors
  EXECUTE 'DROP VIEW IF EXISTS public.v_fish_overview CASCADE';

  -- Baseline-safe overview: fish + aggregated alleles (no external deps)
  CREATE VIEW public.v_fish_overview AS
  SELECT
    f.id                                  AS id,
    f.fish_code                           AS fish_code,
    f.name                                AS name,
    /* comma-joined base codes */
    (
      SELECT array_to_string(array_agg(x.base), ', ')
      FROM (
        SELECT DISTINCT t.transgene_base_code AS base
        FROM public.fish_transgene_alleles t
        WHERE t.fish_id = f.id
        ORDER BY t.transgene_base_code
      ) x
    ) AS transgene_base_code_filled,
    /* comma-joined allele numbers (as text) */
    (
      SELECT array_to_string(array_agg(x.an), ', ')
      FROM (
        SELECT DISTINCT (t.allele_number::text) AS an
        FROM public.fish_transgene_alleles t
        WHERE t.fish_id = f.id
        ORDER BY (t.allele_number::text)
      ) x
    ) AS allele_code_filled,
    NULL::text                            AS allele_name_filled,
    f.created_at                          AS created_at,
    f.created_by                          AS created_by
  FROM public.fish f;
END
$$;

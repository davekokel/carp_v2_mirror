DO $$
BEGIN
  IF to_regclass('public.fish') IS NOT NULL THEN
    EXECUTE $V$
      CREATE OR REPLACE VIEW public.v_fish_overview
      (id, fish_code, name, transgene_base_code_filled, allele_code_filled, allele_name_filled, created_at, created_by) AS
      SELECT
        f.id,                                -- keep id to match prior view
        f.fish_code,
        f.name,                              -- if you later want fish_name, change loaders; keep column name stable here
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
        NULL::text                            AS allele_name_filled,
        f.created_at,
        f.created_by
      FROM public.fish f;
    $V$;
  END IF;
END
$$;

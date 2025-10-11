BEGIN;

-- Base view: only fish that have at least one linked allele
DROP VIEW IF EXISTS public.v_fish_overview CASCADE;
CREATE VIEW public.v_fish_overview AS
SELECT
  f.id,
  f.fish_code,
  f.name,
  (
    SELECT array_to_string(array_agg(x.base ORDER BY x.base), ', ')
    FROM (
      SELECT DISTINCT t.transgene_base_code AS base
      FROM public.fish_transgene_alleles t
      WHERE t.fish_id = f.id
    ) x
  ) AS transgene_base_code_filled,
  (
    SELECT array_to_string(array_agg(x.num::text ORDER BY x.num), ', ')
    FROM (
      SELECT DISTINCT t.allele_number AS num
      FROM public.fish_transgene_alleles t
      WHERE t.fish_id = f.id
    ) x
  ) AS allele_code_filled,
  NULL::text AS allele_name_filled,
  f.created_at,
  f.created_by
FROM public.fish f
WHERE EXISTS (SELECT 1 FROM public.fish_transgene_alleles t WHERE t.fish_id = f.id)
ORDER BY f.created_at DESC;

-- Label view: adapt to optional columns on public.fish
DO $$
DECLARE
  has_nick    boolean;
  has_stage   boolean;
  has_dob     boolean;
  has_dob_alt boolean;
  sql         text;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='nickname'
  ) INTO has_nick;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='line_building_stage'
  ) INTO has_stage;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='date_birth'
  ) INTO has_dob;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='date_of_birth'
  ) INTO has_dob_alt;

  sql := 'CREATE VIEW public.vw_fish_overview_with_label AS
          SELECT
            v.id,
            v.fish_code,
            v.name,
            v.transgene_base_code_filled,
            v.allele_code_filled,
            v.allele_name_filled,
            v.created_at,
            v.created_by,
            CASE
              WHEN v.transgene_base_code_filled IS NOT NULL AND v.allele_code_filled IS NOT NULL
              THEN v.transgene_base_code_filled || '' : '' || v.allele_code_filled
              ELSE NULL
            END AS transgene_pretty,';

  IF has_nick THEN
    sql := sql || ' f.nickname,';
  ELSE
    sql := sql || ' NULL::text AS nickname,';
  END IF;

  IF has_stage THEN
    sql := sql || ' f.line_building_stage,';
  ELSE
    sql := sql || ' NULL::text AS line_building_stage,';
  END IF;

  IF has_dob THEN
    sql := sql || ' f.date_birth,';
  ELSIF has_dob_alt THEN
    sql := sql || ' f.date_of_birth AS date_birth,';
  ELSE
    sql := sql || ' NULL::date AS date_birth,';
  END IF;

  sql := sql || '
            NULL::text        AS batch_label,
            NULL::text        AS created_by_enriched,
            NULL::timestamptz AS last_plasmid_injection_at,
            NULL::text        AS plasmid_injections_text,
            NULL::timestamptz AS last_rna_injection_at,
            NULL::text        AS rna_injections_text
          FROM public.v_fish_overview v
          LEFT JOIN public.fish f ON f.id = v.id
          ORDER BY v.created_at DESC;';

  EXECUTE 'DROP VIEW IF EXISTS public.vw_fish_overview_with_label CASCADE';
  EXECUTE sql;
END$$;

COMMIT;

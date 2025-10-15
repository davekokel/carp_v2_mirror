BEGIN;
DO 28762
DECLARE
  has_nick  boolean;
  has_stage boolean;
  has_dob   boolean;
  has_dob_alt boolean;
  sql text;
BEGIN
  -- which optional columns exist on public.fish?
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

  -- Build the CREATE VIEW text safely
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
              WHEN v.transgene_base_code_filled IS NOT NULL
               AND v.allele_code_filled IS NOT NULL
              THEN v.transgene_base_code_filled || '' : '' || v.allele_code_filled
              ELSE NULL
            END AS transgene_pretty,';

  -- nickname
  IF has_nick THEN
    sql := sql || ' f.nickname,';
  ELSE
    sql := sql || ' NULL::text AS nickname,';
  END IF;

  -- line_building_stage
  IF has_stage THEN
    sql := sql || ' f.line_building_stage,';
  ELSE
    sql := sql || ' NULL::text AS line_building_stage,';
  END IF;

  -- date_birth (prefer date_birth; fall back to date_of_birth)
  IF has_dob THEN
    sql := sql || ' f.date_birth,';
  ELSIF has_dob_alt THEN
    sql := sql || ' f.date_of_birth AS date_birth,';
  ELSE
    sql := sql || ' NULL::date AS date_birth,';
  END IF;

  -- simple placeholders for now (until you add the injection roll-ups again)
  sql := sql || '
            NULL::text        AS batch_label,
            NULL::text        AS created_by_enriched,
            NULL::timestamptz AS last_plasmid_injection_at,
            NULL::text        AS plasmid_injections_text,
            NULL::timestamptz AS last_rna_injection_at,
            NULL::text        AS rna_injections_text
          FROM public.v_fish_overview v
          LEFT JOIN public.fish f
                 ON f.id = v.id;';

  -- Drop and recreate safely
  EXECUTE 'DROP VIEW IF EXISTS public.vw_fish_overview_with_label CASCADE';
  EXECUTE sql;
END$$;

COMMIT;

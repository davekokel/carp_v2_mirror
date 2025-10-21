BEGIN;

-- Rebuild v_fish_overview_with_label dynamically depending on which fish.* columns exist
DO $$
DECLARE
  has_nick boolean;
  has_stage boolean;
  has_dob boolean;
  join_fish boolean;
  sql text;
  nick_expr  text;
  stage_expr text;
  dob_expr   text;
  join_clause text := '';
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

  -- decide expressions
  nick_expr  := CASE WHEN has_nick  THEN 'f.nickname'             ELSE 'NULL::text'        END || ' AS nickname';
  stage_expr := CASE WHEN has_stage THEN 'f.line_building_stage'   ELSE 'NULL::text'        END || ' AS line_building_stage';
  dob_expr   := CASE WHEN has_dob   THEN 'f.date_birth'            ELSE 'NULL::date'        END || ' AS date_birth';

  join_fish := has_nick OR has_stage OR has_dob;
  IF join_fish THEN
    join_clause := 'LEFT JOIN public.fish f ON f.id = v.id';
  END IF;

  -- Drop old view if present
  EXECUTE 'DROP VIEW IF EXISTS public.v_fish_overview_with_label';

  -- Build CREATE VIEW text
  sql := format($FMT$
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
      CASE
        WHEN v.transgene_base_code_filled IS NOT NULL AND v.allele_code_filled IS NOT NULL
        THEN v.transgene_base_code_filled || ' : ' || v.allele_code_filled
        ELSE NULL
      END AS transgene_pretty,
      %s,
      %s,
      %s,
      NULL::text        AS batch_label,
      NULL::text        AS created_by_enriched,
      NULL::timestamptz AS last_plasmid_injection_at,
      NULL::text        AS plasmid_injections_text,
      NULL::timestamptz AS last_rna_injection_at,
      NULL::text        AS rna_injections_text
    FROM public.v_fish_overview v
    %s
    ORDER BY v.created_at DESC
  $FMT$, nick_expr, stage_expr, dob_expr, join_clause);

  -- Create the view
  EXECUTE sql;
END
$$;

COMMIT;

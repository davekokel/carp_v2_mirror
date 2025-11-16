BEGIN;

DROP VIEW IF EXISTS public.v_treated_clutches_overview CASCADE;

-- Build v_treated_clutches_overview in a schema-flexible way.
-- It tolerates any of these columns on public.clutch_instances:
--   clutch_genotype_pretty | clutch_genotype | genotype_pretty | genotype
DO $$
DECLARE
  cols_present text[];
  coalesce_expr text;
BEGIN
  SELECT array_agg(c.column_name ORDER BY c.ordinal_position)
  INTO cols_present
  FROM information_schema.columns c
  WHERE c.table_schema='public'
    AND c.table_name='clutch_instances'
    AND c.column_name IN ('clutch_genotype_pretty','clutch_genotype','genotype_pretty','genotype');

  IF cols_present IS NULL OR array_length(cols_present,1) IS NULL THEN
    coalesce_expr := '''''';  -- fallback to empty string
  ELSE
    coalesce_expr := 'COALESCE(' ||
                     array_to_string(ARRAY(
                       SELECT 'ci.'||quote_ident(x) FROM unnest(cols_present) AS x
                     ), ', ') || ', '''')';
  END IF;

  EXECUTE format($v$
    CREATE VIEW public.v_treated_clutches_overview AS
    WITH base AS (
      SELECT
        ci.id                                    AS clutch_instance_id,
        ci.clutch_instance_code                  AS clutch_code,
        %s                                       AS clutch_genotype,
        cr.id                                    AS cross_id,
        COALESCE(cr.cross_run_code, cr.id::text) AS cross_code,
        cr.tank_pair_id
      FROM public.clutch_instances ci
      LEFT JOIN public.crosses cr ON cr.id = ci.cross_instance_id
    ),
    tx_raw AS (
      SELECT
        tc.treated_clutch_code,
        tc.created_at                 AS group_created_at,
        b.clutch_instance_id,
        b.clutch_code,
        b.clutch_genotype,
        b.cross_code,
        b.tank_pair_id,
        NULLIF(t.treat_code,'')                         AS code,
        NULLIF(COALESCE(t.treat_text,t.treat_code),'')  AS name
      FROM public.treated_clutches tc
      JOIN base b                         ON b.clutch_instance_id = tc.clutch_instance_id
      LEFT JOIN public.join_clutch_treatments jct ON jct.treated_clutch_id = tc.id
      LEFT JOIN public.treatments t                ON t.id = jct.treatment_id
    ),
    tx_distinct AS (
      SELECT DISTINCT
        treated_clutch_code,
        group_created_at,
        clutch_instance_id,
        clutch_code,
        clutch_genotype,
        cross_code,
        tank_pair_id,
        code,
        name
      FROM tx_raw
    ),
    grp AS (
      SELECT
        td.treated_clutch_code,
        MIN(td.group_created_at)                                  AS group_created_at,
        MIN(td.clutch_instance_id::text)                          AS clutch_instance_id,  -- avoid min(uuid)
        MIN(td.clutch_code)                                       AS clutch_code,
        MIN(td.clutch_genotype)                                   AS clutch_genotype,
        MIN(td.cross_code)                                        AS cross_code,
        MIN(td.tank_pair_id::text)                                AS tank_pair_id_text,
        COUNT(td.code)                                            AS treatments_count_group,
        COALESCE(string_agg(td.code, '+'   ORDER BY td.code), '') AS treatments_codes_group,
        COALESCE(string_agg(td.name, ' + ' ORDER BY td.name), '') AS treatments_names_group
      FROM tx_distinct td
      GROUP BY td.treated_clutch_code
    ),
    tm AS (
      SELECT id::uuid AS tank_id, tank_code, fish_code
      FROM public.v_tanks_overview
    ),
    geno AS (
      SELECT fish_code_raw AS fish_code, MAX(genotype_pretty) AS genotype
      FROM public.v_fish_overview
      GROUP BY fish_code_raw
    )
    SELECT
      g.treated_clutch_code,
      g.group_created_at,
      g.clutch_instance_id,        -- text
      g.clutch_code,
      g.clutch_genotype,
      g.cross_code,
      g.treatments_count_group,
      g.treatments_codes_group,
      g.treatments_names_group,
      tm_m.fish_code AS mom_fish_code,
      tm_d.fish_code AS dad_fish_code,
      gm.genotype    AS mom_genotype,
      gd.genotype    AS dad_genotype
    FROM grp g
    LEFT JOIN public.tank_pairs tp ON tp.id = g.tank_pair_id_text::uuid
    LEFT JOIN tm    AS tm_m ON tm_m.tank_id = tp.mother_tank_id
    LEFT JOIN tm    AS tm_d ON tm_d.tank_id = tp.father_tank_id
    LEFT JOIN geno  AS gm   ON gm.fish_code = tm_m.fish_code
    LEFT JOIN geno  AS gd   ON gd.fish_code = tm_d.fish_code
    ORDER BY g.clutch_code, g.group_created_at;
  $v$, coalesce_expr);
END$$;

COMMIT;

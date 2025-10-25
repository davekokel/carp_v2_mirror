DO $body$
DECLARE
  v_schema text := 'public';
  v_view   text := 'v_tank_pairs';
  v_bak    text := v_view || '__bak_' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISS');
  dep record;
BEGIN
  -- 1) Capture dependents
  CREATE TEMP TABLE tmp_dep AS
  SELECT n.nspname AS view_schema,
         c.relname AS view_name,
         pg_get_viewdef(c.oid, true) AS def
  FROM pg_depend d
  JOIN pg_rewrite r ON r.oid = d.objid
  JOIN pg_class c ON c.oid = r.ev_class AND c.relkind = 'v'
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE d.refclassid = 'pg_class'::regclass
    AND d.refobjid   = format('%I.%I', v_schema, v_view)::regclass;

  -- 2) Rename old view
  EXECUTE format('ALTER VIEW %I.%I RENAME TO %I', v_schema, v_view, v_bak);

  -- 3) Recreate new main view
  EXECUTE format($sql$
    CREATE OR REPLACE VIEW %I.%I AS
    WITH latest_clutch AS (
      SELECT fish_pair_id, clutch_code, expected_genotype,
             row_number() OVER (PARTITION BY fish_pair_id ORDER BY created_at DESC NULLS LAST) rn
      FROM %I.clutches
    )
    SELECT
      tp.id,
      tp.tank_pair_code,
      tp.status,
      tp.role_orientation,
      tp.concept_id,
      tp.fish_pair_id,
      tp.created_by,
      tp.created_at,
      tp.updated_at,
      tp.mother_tank_id,
      COALESCE(tp.mom_tank_code, mt.tank_code) AS mom_tank_code,
      mt.fish_code AS mom_fish_code,
      tp.mom_genotype,
      tp.father_tank_id,
      COALESCE(tp.dad_tank_code, dt.tank_code) AS dad_tank_code,
      dt.fish_code AS dad_fish_code,
      tp.dad_genotype,
      (mt.fish_code || ' × ' || dt.fish_code) AS pair_fish,
      (COALESCE(tp.mom_tank_code, mt.tank_code) || ' × ' ||
       COALESCE(tp.dad_tank_code, dt.tank_code)) AS pair_tanks,
      CASE
        WHEN NULLIF(lc.expected_genotype,'') IS NOT NULL THEN lc.expected_genotype
        WHEN NULLIF(tp.mom_genotype,'') IS NOT NULL AND NULLIF(tp.dad_genotype,'') IS NOT NULL
          THEN tp.mom_genotype || ' × ' || tp.dad_genotype
        ELSE NULLIF(tp.mom_genotype,'')
      END AS pair_genotype,
      lc.clutch_code
    FROM %I.%I tp
    LEFT JOIN %I.tanks mt ON mt.tank_id = tp.mother_tank_id
    LEFT JOIN %I.tanks dt ON dt.tank_id = tp.father_tank_id
    LEFT JOIN latest_clutch lc ON lc.fish_pair_id = tp.fish_pair_id AND lc.rn = 1
    ORDER BY tp.created_at DESC NULLS LAST;
  $sql$, v_schema, v_view, v_schema, v_schema, v_bak, v_schema, v_schema);

  -- 4) Rebuild dependents
  FOR dep IN SELECT * FROM tmp_dep LOOP
    EXECUTE format('CREATE OR REPLACE VIEW %I.%I AS %s', dep.view_schema, dep.view_name, dep.def);
  END LOOP;

  -- 5) Drop backup
  EXECUTE format('DROP VIEW IF EXISTS %I.%I', v_schema, v_bak);

  -- 6) Clean old pretty
  IF EXISTS (
    SELECT 1 FROM information_schema.views
     WHERE table_schema=v_schema AND table_name='v_tank_pairs_pretty'
  ) THEN
    EXECUTE format('DROP VIEW %I.%I', v_schema, 'v_tank_pairs_pretty');
  END IF;
END
$body$;

COMMENT ON VIEW public.v_tank_pairs IS
  'Snapshot-aware tank pairs with pretty helpers (pair_fish, pair_tanks, pair_genotype, clutch_code).';

COMMIT;

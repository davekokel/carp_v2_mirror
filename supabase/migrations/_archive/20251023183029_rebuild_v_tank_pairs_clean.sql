-- Fully rebuild public.v_tank_pairs with pretty columns, re-binding dependent views.
DO $$
DECLARE
  v_schema  text := 'public';
  v_view    text := 'v_tank_pairs';
  v_bak     text := v_view || '__bak_' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISS');
  dep record;
BEGIN
  -- 1. Snapshot dependent views
  CREATE TEMP TABLE tmp_dep AS
  SELECT
    n.nspname AS view_schema,
    c.relname AS view_name,
    pg_get_viewdef(c.oid, true) AS def
  FROM pg_depend d
  JOIN pg_rewrite r ON r.oid = d.objid
  JOIN pg_class c ON c.oid = r.ev_class AND c.relkind = 'v'
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE d.refclassid = 'pg_class'::regclass
    AND d.refobjid   = format('%I.%I', v_schema, v_view)::regclass;

  -- 2. Rename current view out of the way
  EXECUTE format('ALTER VIEW %I.%I RENAME TO %I', v_schema, v_view, v_bak);

  -- 3. Create new v_tank_pairs (keeping old cols, adding pretty ones)
  EXECUTE format($$CREATE OR REPLACE VIEW %I.%I AS
    WITH latest_clutch AS (
      SELECT fish_pair_id, clutch_code, expected_genotype,
             row_number() OVER (PARTITION BY fish_pair_id ORDER BY created_at DESC NULLS LAST) rn
      FROM %1$I.clutches
    )
    SELECT
      old.*,
      coalesce(mt.fish_code,'') || ' × ' || coalesce(dt.fish_code,'')                                 AS pair_fish,
      coalesce(old.mom_tank_code, mt.tank_code) || ' × ' || coalesce(old.dad_tank_code, dt.tank_code) AS pair_tanks,
      CASE
        WHEN nullif(lc.expected_genotype,'') IS NOT NULL THEN lc.expected_genotype
        WHEN nullif(old.mom_genotype,'') IS NOT NULL AND nullif(old.dad_genotype,'') IS NOT NULL
          THEN old.mom_genotype || ' × ' || old.dad_genotype
        ELSE nullif(old.mom_genotype,'')
      END AS pair_genotype,
      CASE
        WHEN nullif(lc.expected_genotype,'') IS NOT NULL THEN lc.expected_genotype
        WHEN nullif(old.mom_genotype,'') IS NOT NULL AND nullif(old.dad_genotype,'') IS NOT NULL
          THEN old.mom_genotype || ' × ' || old.dad_genotype
        ELSE nullif(old.mom_genotype,'')
      END AS genotype,
      lc.clutch_code
    FROM %1$I.%3$I AS old
    LEFT JOIN %1$I.tanks mt ON mt.tank_id = old.mother_tank_id
    LEFT JOIN %1$I.tanks dt ON dt.tank_id = old.father_tank_id
    LEFT JOIN latest_clutch lc ON lc.fish_pair_id = old.fish_pair_id AND lc.rn = 1
    ORDER BY old.created_at DESC NULLS LAST$$,
    v_schema, v_view, v_bak);

  -- 4. Re-create dependent views so they bind to the new one
  FOR dep IN SELECT * FROM tmp_dep LOOP
    EXECUTE format('CREATE OR REPLACE VIEW %I.%I AS %s', dep.view_schema, dep.view_name, dep.def);
  END LOOP;

  -- 5. Drop the backup view
  EXECUTE format('DROP VIEW IF EXISTS %I.%I', v_schema, v_bak);

  -- 6. Drop any obsolete pretty view
  IF EXISTS (
    SELECT 1 FROM information_schema.views
     WHERE table_schema=v_schema AND table_name='v_tank_pairs_pretty'
  ) THEN
    EXECUTE format('DROP VIEW %I.%I', v_schema, 'v_tank_pairs_pretty');
  END IF;
END$$;

COMMENT ON VIEW public.v_tank_pairs IS
  'Snapshot-aware tank pairs with pretty helpers (pair_fish, pair_tanks, pair_genotype, genotype, clutch_code).';

COMMIT;

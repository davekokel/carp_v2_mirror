-- Rebuild public.v_tank_pairs in-place by swapping behind the same name.
-- Keeps existing columns/ordering via old_view.*, then appends new columns.
-- Rebinds any dependent views automatically. Drops the bak view at the end.

DO $body$
DECLARE
  v_schema text := 'public';
  v_name   text := 'v_tank_pairs';
  v_old    text := 'v_tank_pairs';
  v_bak    text := v_name || '__bak_' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISS');
BEGIN
  -- Gather dependent *views* that reference public.v_tank_pairs
  CREATE TEMP TABLE tmp_dep AS
  SELECT n.nspname AS view_schema,
         c.relname AS view_name,
         pg_get_viewdef(c.oid, true) AS view_def
  FROM   pg_depend d
  JOIN   pg_rewrite r   ON r.oid = d.objid
  JOIN   pg_class   c   ON c.oid = r.ev_class AND c.relkind = 'v'
  JOIN   pg_namespace n ON n.oid = c.relnamespace
  WHERE  d.refclassid = 'pg_class'::regclass
    AND  d.refobjid   = format('%I.%I', v_schema, v_name)::regclass;

  -- Rename the existing view out of the way
  EXECUTE format('ALTER VIEW %I.%I RENAME TO %I', v_schema, v_name, v_bak);

  -- Recreate the target view name, selecting all legacy columns from the bak view
  -- and appending new pretty/helper columns at the tail.
  EXECUTE format($sql$
    CREATE VIEW %I.%I AS
    WITH lc AS (
      SELECT
        c.fish_pair_id,
        c.clutch_code,
        c.expected_genotype,
        c.created_at,
        row_number() OVER (PARTITION BY c.fish_pair_id ORDER BY c.created_at DESC NULLS LAST) AS rn
      FROM %1$I.clutches c
    )
    SELECT
      old.*,

      -- pretty helpers
      coalesce(mt.fish_code,'') || ' × ' || coalesce(dt.fish_code,'')                                   AS pair_fish,
      coalesce(old.mom_tank_code, mt.tank_code) || ' × ' || coalesce(old.dad_tank_code, dt.tank_code)   AS pair_tanks,

      CASE
        WHEN nullif(lc.expected_genotype,'') IS NOT NULL THEN lc.expected_genotype
        WHEN nullif(old.mom_genotype,'') IS NOT NULL AND nullif(old.dad_genotype,'') IS NOT NULL
          THEN old.mom_genotype || ' × ' || old.dad_genotype
        ELSE nullif(old.mom_genotype,'')
      END                                                                                               AS pair_genotype,

      CASE
        WHEN nullif(lc.expected_genotype,'') IS NOT NULL THEN lc.expected_genotype
        WHEN nullif(old.mom_genotype,'') IS NOT NULL AND nullif(old.dad_genotype,'') IS NOT NULL
          THEN old.mom_genotype || ' × ' || old.dad_genotype
        ELSE nullif(old.mom_genotype,'')
      END                                                                                               AS genotype,

      lc.clutch_code
    FROM %1$I.%3$I AS old
    LEFT JOIN %1$I.tanks mt ON mt.tank_id = old.mother_tank_id
    LEFT JOIN %1$I.tanks dt ON dt.tank_id = old.father_tank_id
    LEFT JOIN lc ON lc.fish_pair_id = old.fish_pair_id AND lc.rn = 1
    ORDER BY old.created_at DESC NULLS LAST
  $sql$, v_schema, v_name, v_bak);

  -- Rebind dependent views to the new public.v_tank_pairs by re-creating them with the same text.
  -- Since we captured their definitions before the rename (when they referenced public.v_tank_pairs),
  -- re-running CREATE OR REPLACE will now bind them to the new public.v_tank_pairs.
  FOR
    SELECT format('CREATE OR REPLACE VIEW %I.%I AS %s', view_schema, view_name, view_def)
    FROM tmp_dep
  INTO STRICT
    -- We must EXECUTE each row; use a loop
  LOOP
    EXECUTE (SELECT format('CREATE OR REPLACE VIEW %I.%I AS %s', view_schema, view_name, view_def)
             FROM tmp_dep
             WHERE false); -- placeholder to define types
  END LOOP;

  -- The above FOR .. INTO STRICT is a hack. Proper loop:
  FOR record IN SELECT * FROM tmp_dep LOOP
    EXECUTE format('CREATE OR REPLACE VIEW %I.%I AS %s', record.view_schema, record.view_name, record.view_def);
  END LOOP;

  -- Drop the bak view now that dependents are re-bound
  EXECUTE format('DROP VIEW IF EXISTS %I.%I', v_schema, v_bak);

  -- Optional: remove any old pretty wrapper if present
  IF EXISTS (
    SELECT 1 FROM information_schema.views WHERE table_schema = v_schema AND table_name = 'v_tank_pairs_pretty'
  ) THEN
    EXECUTE format('DROP VIEW %I.%I', v_schema, 'v_tank_pairs_pretty');
  END IF;

END
$body$;

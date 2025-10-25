-- Rebuild public.v_tank_pairs in-place without breaking dependent views.
-- 1) Capture dependent views (their CREATE text)
-- 2) RENAME old v_tank_pairs → v_tank_pairs__bak_<timestamp>
-- 3) CREATE new public.v_tank_pairs selecting bak.* + new pretty columns
-- 4) Re-create dependent views from captured SQL (they now bind to the new v_tank_pairs)
-- 5) DROP the bak view
-- 6) Optionally DROP public.v_tank_pairs_pretty (if exists)

DO $body$
DECLARE
  v_schema  text := 'public';
  v_view    text := 'v_tank_pairs';
  v_bak     text := v_view || '__bak_' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISS');
  dep_rec   record;
  dep_sql   text;
BEGIN
  -- 1) Snapshot dependent view definitions
  CREATE TEMP TABLE tmp_dep_views AS
  SELECT
    n.nspname                                        AS view_schema,
    c.relname                                        AS view_name,
    'CREATE OR REPLACE VIEW ' || quote_ident(n.nspname) || '.' || quote_ident(c.relname) || E' AS\n' ||
    pg_get_viewdef(c.oid, true)                      AS create_sql
  FROM   pg_depend d
  JOIN   pg_rewrite r        ON r.oid = d.objid
  JOIN   pg_class   c        ON c.oid = r.ev_class AND c.relkind = 'v'
  JOIN   pg_namespace n      ON n.oid = c.relnamespace
  WHERE  d.refclassid = 'pg_class'::regclass
     AND d.refobjid   = format('%I.%I', v_schema, v_view)::regclass;

  -- 2) Rename the old view out of the way
  EXECUTE format('ALTER VIEW %I.%I RENAME TO %I', v_schema, v_view, v_bak);

  -- 3) Create the new public.v_tank_pairs reusing all old columns (old.*) and appending pretty fields
  EXECUTE format($sql$
    CREATE VIEW %I.%I AS
    WITH latest_clutch AS (
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
      coalesce(mt.fish_code,'') || ' × ' || coalesce(dt.fish_code,'')                                 AS pair_fish,
      coalesce(old.mom_tank_code, mt.tank_code) || ' × ' || coalesce(old.dad_tank_code, dt.tank_code) AS pair_tanks,

      CASE
        WHEN nullif(lc.expected_genotype,'') IS NOT NULL THEN lc.expected_genotype
        WHEN nullif(old.mom_genotype,'') IS NOT NULL AND nullif(old.dad_genotype,'') IS NOT NULL
          THEN old.mom_genotype || ' × ' || old.dad_genotype
        ELSE nullif(old.mom_genotype,'')
      END                                                                                              AS pair_genotype,

      CASE
        WHEN nullif(lc.expected_genotype,'') IS NOT NULL THEN lc.expected_genotype
        WHEN nullif(old.mom_genotype,'') IS NOT NULL AND nullif(old.dad_genotype,'') IS NOT NULL
          THEN old.mom_genotype || ' × ' || old.dad_genotype
        ELSE nullif(old.mom_genotype,'')
      END                                                                                              AS genotype,

      lc.clutch_code
    FROM %1$I.%3$I AS old
    LEFT JOIN %1$I.tanks mt ON mt.tank_id = old.mother_tank_id
    LEFT JOIN %1$I.tanks dt ON dt.tank_id = old.father_tank_id
    LEFT JOIN latest_clutch lc ON lc.fish_pair_id = old.fish_pair_id AND lc.rn = 1
    ORDER BY old.created_at DESC NULLS LAST
  $sql$, v_schema, v_view, v_bak);

  -- 4) Re-create dependent views to bind them to the new v_tank_pairs
  FOR dep_rec IN
    SELECT view_schema, view_name, create_sql FROM tmp_dep_views ORDER BY view_schema, view_name
  LOOP
    dep_sql := dep_rec.create_sql;
    -- Recreate the view
    EXECUTE dep_sql;
  END LOOP;

  -- 5) Drop the bak view now that dependents are rebound
  EXECUTE format('DROP VIEW IF EXISTS %I.%I', v_schema, v_bak);

  -- 6) Optional cleanup of any old pretty wrapper
  IF EXISTS (
    SELECT 1 FROM information_schema.views WHERE table_schema = v_schema AND table_name = 'v_tank_pairs_pretty'
  ) THEN
    EXECUTE format('DROP VIEW %I.%I', v_schema, 'v_tank_pairs_pretty');
  END IF;
END
$body$;

-- (Optional) re-apply grants here if you had custom ACL on public.v_tank_pairs
-- e.g.: GRANT SELECT ON public.v_tank_pairs TO some_role;


-- Rebuild public.v_tank_pairs in place, preserving legacy columns and order,
-- and append UI-friendly columns (pair_fish, pair_tanks, pair_genotype, genotype, clutch_code).
-- Rebind any dependent views automatically. No new view names are introduced.

DO $do$
DECLARE
  v_schema text := 'public';
  v_view   text := 'v_tank_pairs';
  v_bak    text := v_view || '__bak_' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISS');
  rec      RECORD;
  ddl      text;
  create_main text;
BEGIN
  -- 1) Capture dependent VIEW definitions (as full CREATE OR REPLACE VIEW ... AS <definition>)
  CREATE TEMP TABLE tmp_dep AS
  SELECT
      n.nspname AS view_schema,
      c.relname AS view_name,
      'CREATE OR REPLACE VIEW '
        || quote_ident(n.nspname) || '.' || quote_ident(c.relname)
        || E'\nAS\n' || pg_get_viewdef(c.oid, true) AS ddl
  FROM   pg_depend d
  JOIN   pg_rewrite   r ON r.oid = d.objid
  JOIN   pg_class     c ON c.oid = r.ev_class AND c.relkind = 'v'  -- views only
  JOIN   pg_namespace n ON n.oid = c.relnamespace
  WHERE  d.refclassid = 'pg_class'::regclass
    AND  d.refobjid   = (quote_ident(v_schema)||'.'||quote_ident(v_view))::regclass;

  -- 2) Rename old view out of the way (dependents keep working while we swap)
  EXECUTE format('ALTER VIEW %I.%I RENAME TO %I', v_schema, v_view, v_bak);

  -- 3) Compose new main view definition. Use old.* to preserve legacy column order,
  --    then LEFT JOIN tanks & latest clutch and append the new columns.
  create_main :=
    'CREATE VIEW '||quote_ident(v_schema)||'.'||quote_ident(v_view)||E' AS
     WITH lc AS (
       SELECT c.fish_pair_id, c.clutch_code, c.expected_genotype,
              row_number() OVER (PARTITION BY c.fish_pair_id ORDER BY c.created_at DESC NULLS LAST) AS rn
       FROM '||quote_ident(v_schema)||'.clutches c
     )
     SELECT
       old.*,
       '||
       -- pretty helpers
       'COALESCE(mt.fish_code, '''') || '' × '' || COALESCE(dt.fish_code, '''') AS pair_fish,
        COALESCE(old.mom_tank_code, mt.''||quote_ident('tank_code')||'') || '' × '' ||
          COALESCE(old.dad_tank_code, dt.''||quote_ident('tank_code')||'') AS pair_tanks,
        CASE
          WHEN NULLIF(lc.expected_genotype, '''') IS NOT NULL THEN lc.expected_genotype
          WHEN NULLIF(old.mom_genotype, '''') IS NOT NULL AND NULLIF(old.dad_genotype, '''') IS NOT NULL
            THEN old.mom_genotype || '' × '' || old.dad_genotype
          ELSE NULLIF(old.mom_genotype, '''')
        END AS pair_genotype,
        CASE
          WHEN NULLIF(lc.expected_genotype, '''') IS NOT NULL THEN lc.expected_genotype
          WHEN NULLIF(old.mom_genotype, '''') IS NOT NULL AND NULLIF(old.dad_genotype, '''') IS NOT NULL
            THEN old.mom_genotype || '' × '' || old.dad_genotype
          ELSE NULLIF(old.mom_genotype, '''')
        END AS genotype,
        lc.clutch_code
     FROM '||quote_ident(v_schema)||'.'||quote_ident(v_bak)||' AS old
     LEFT JOIN '||quote_ident(v_schema)||'.tanks AS mt ON mt.'||quote_ident('tank_id')||' = old.'||quote_ident('mother_tank_id')||'
     LEFT JOIN '||quote_ident(v_schema)||'.tanks AS dt ON dt.'||quote_ident('tank_id')||' = old.'||quote_ident('father_tank_id')||'
     LEFT JOIN lc ON lc.fish_pair_id = old.fish_pair_id AND lc.rn = 1
     ORDER BY old.created_at DESC NULLS LAST';

  EXECUTE create_main;

  -- 4) Recreate each dependent view so it binds to the new v_tank_pairs
  FOR rec IN SELECT ddl FROM tmp_dep ORDER BY 1 LOOP
    ddl := rec.ddl;
    EXECUTE ddl;
  END LOOP;

  -- 5) Drop the backup view
  EXECUTE format('DROP VIEW IF EXISTS %I.%I', v_schema, v_bak);

  -- 6) Optional: drop any obsolete pretty wrapper
  IF EXISTS (
    SELECT 1 FROM information_schema.views
     WHERE table_schema = v_schema AND table_name = 'v_tank_pairs_pretty'
  ) THEN
    EXECUTE format('DROP VIEW %I.%I', v_schema, 'v_tank_pairs_pretty');
  END IF;
END
$do$;

COMMENT ON VIEW public.v_tank_pairs IS
  'Snapshot-aware tank pairs with appended helpers: pair_fish, pair_tanks, pair_genotype, genotype, clutch_code.';

-- Rebuild public.v_tank_pairs in place with appended pretty columns,
-- rebind any dependent views, and drop any obsolete v_tank_pairs_pretty.

DO $$
DECLARE
  v_bak text := 'v_tank_pairs__bak_' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISS');
  dep   record;
BEGIN
  -- 1) Snapshot dependent views that reference public.v_tank_pairs
  CREATE TEMP TABLE tmp_dep AS
  SELECT
      n.nspname AS view_schema,
      c.relname AS view_name,
      'CREATE OR REPLACE VIEW '
        || quote_ident(n.nspname) || '.' || quote_ident(c.relname)
        || E'\nAS\n' || pg_get_viewdef(c.oid, true) AS ddl
  FROM   pg_depend d
  JOIN   pg_rewrite   r ON r.iod = d.oid    -- NOTE: see below, fixed in next line
  WHERE  false;
END$$;

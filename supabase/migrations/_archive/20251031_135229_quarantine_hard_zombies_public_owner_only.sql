DO $$
DECLARE
  trash text := 'trash_carp';
  owner_oid oid := (SELECT oid FROM pg_roles WHERE rolname = current_user);
  rec record;
BEGIN
  EXECUTE format('create schema if not exists %I', trash);

  FOR rec IN
    WITH rels AS (
      SELECT n.nspname AS schema_name, c.relname AS table_name, c.oid, c.relowner
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE c.relkind IN ('r','p') AND n.nspname='public'
    ),
    stats AS (
      SELECT relid,
             COALESCE(seq_scan,0)+COALESCE(idx_scan,0) AS scans,
             COALESCE(n_tup_ins,0)+COALESCE(n_tup_upd,0)+COALESCE(n_tup_del,0) AS iud_total,
             COALESCE(n_live_tup,0) AS row_est
      FROM pg_stat_all_tables
    ),
    deps AS (
      SELECT confrelid AS oid FROM pg_constraint WHERE contype='f'
      UNION
      SELECT d.refobjid AS oid
      FROM pg_depend d
      JOIN pg_rewrite r ON r.oid = d.objid
      JOIN pg_class v ON v.oid = r.ev_class
      WHERE v.relkind IN ('v','m')
      UNION
      SELECT d.refobjid AS oid FROM pg_depend d WHERE d.classid='pg_proc'::regclass
    )
    SELECT r.schema_name, r.table_name
    FROM rels r
    LEFT JOIN stats s ON s.relid = r.oid
    LEFT JOIN deps  d ON d.oid = r.oid
    WHERE r.relowner = owner_oid
      AND d.oid IS NULL
      AND COALESCE(s.scans,0)=0
      AND COALESCE(s.iud_total,0)=0
      AND COALESCE(s.row_est,0)=0
  LOOP
    IF to_regclass(format('%I.%I', trash, rec.table_name)) IS NULL THEN
      EXECUTE format('ALTER TABLE %I.%I SET SCHEMA %I', rec.schema_name, rec.table_name, trash);
    END IF;
  END LOOP;
END $$;

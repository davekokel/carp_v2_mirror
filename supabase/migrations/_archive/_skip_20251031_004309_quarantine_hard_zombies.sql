DO $$
DECLARE
  trash text := 'trash_carp';
  rec record;
BEGIN
  EXECUTE format('create schema if not exists %I', trash);
  FOR rec IN
    WITH rels AS (
      SELECT n.nspname AS schema_name, c.relname AS table_name, c.oid
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE c.relkind IN ('r','p') AND n.nspname NOT IN ('pg_catalog','information_schema')
    ), stats AS (
      SELECT relid,
             COALESCE(seq_scan,0)+COALESCE(idx_scan,0) AS scans,
             COALESCE(n_tup_ins,0)+COALESCE(n_tup_upd,0)+COALESCE(n_tup_del,0) AS iud_total,
             COALESCE(n_live_tup,0) AS row_est
      FROM pg_stat_all_tables
    ), fk_refs AS (
      SELECT confrelid AS oid, COUNT(*) AS n_fk_refs FROM pg_constraint WHERE contype='f' GROUP BY confrelid
    ), view_refs AS (
      SELECT d.refobjid AS oid, COUNT(*) AS n_view_refs
      FROM pg_depend d JOIN pg_rewrite r ON r.oid=d.objid JOIN pg_class v ON v.oid=r.ev_class
      WHERE v.relkind IN ('v','m') GROUP BY d.refobjid
    ), func_refs AS (
      SELECT d.refobjid AS oid, COUNT(*) AS n_func_refs FROM pg_depend d WHERE d.classid='pg_proc'::regclass GROUP BY d.refobjid
    )
    SELECT r.schema_name, r.table_name
    FROM rels r
    LEFT JOIN stats s  ON s.relid = r.oid
    LEFT JOIN fk_refs fr ON fr.oid = r.oid
    LEFT JOIN view_refs vr ON vr.oid = r.oid
    LEFT JOIN func_refs pr ON pr.oid = r.oid
    WHERE COALESCE(fr.n_fk_refs,0)+COALESCE(vr.n_view_refs,0)+COALESCE(pr.n_func_refs,0)=0
      AND COALESCE(s.scans,0)=0
      AND COALESCE(s.iud_total,0)=0
      AND COALESCE(s.row_est,0)=0
  LOOP
    IF to_regclass(format('%I.%I', trash, rec.table_name)) IS NULL THEN
      EXECUTE format('alter table %I.%I set schema %I', rec.schema_name, rec.table_name, trash);
    END IF;
  END LOOP;
END$$;

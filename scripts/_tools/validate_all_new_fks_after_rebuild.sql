WITH c AS (
  SELECT n.nspname, rel.relname AS table_name, con.conname
  FROM pg_constraint con
  JOIN pg_class rel ON rel.oid=con.conrelid
  JOIN pg_namespace n ON n.oid=rel.relnamespace
  WHERE n.nspname='public'
    AND con.contype='f'
    AND con.convalidated = false
)
SELECT format('ALTER TABLE %I.%I VALIDATE CONSTRAINT %I;', nspname, table_name, conname)
FROM c
ORDER BY table_name, conname;
\gexec

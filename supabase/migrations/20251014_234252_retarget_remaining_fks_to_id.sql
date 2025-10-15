-- Rewrite any remaining single-column FKs that reference parent(id_uuid) to parent(id)
DO $$
BEGIN
DECLARE
  r RECORD;
  del_action text;
BEGIN
  FOR r IN
    SELECT
      c.conname                              AS fk_name,
      n_child.nspname                        AS child_schema,
      child.relname                          AS child_table,
      a_child.attname                        AS child_col,
      n_parent.nspname                       AS parent_schema,
      parent.relname                         AS parent_table,
      a_parent.attname                       AS parent_col,
      c.confdeltype                          AS deltype
    FROM pg_constraint c
    JOIN pg_class child         ON child.oid = c.conrelid
    JOIN pg_namespace n_child   ON n_child.oid = child.relnamespace AND n_child.nspname='public'
    JOIN pg_class parent        ON parent.oid = c.confrelid
    JOIN pg_namespace n_parent  ON n_parent.oid = parent.relnamespace AND n_parent.nspname='public'
    JOIN LATERAL unnest(c.conkey)  AS ck(k) ON TRUE
    JOIN LATERAL unnest(c.confkey) AS pk(k) ON TRUE
    JOIN pg_attribute a_child     ON a_child.attrelid  = child.oid  AND a_child.attnum  = ck.k
    JOIN pg_attribute a_parent    ON a_parent.attrelid = parent.oid AND a_parent.attnum = pk.k
    WHERE c.contype='f'
      AND a_parent.attname='id_uuid'
      AND cardinality(c.conkey)=1
      AND cardinality(c.confkey)=1
  LOOP
    -- Map internal deltype to SQL keyword
    del_action :=
      CASE r.deltype
        WHEN 'a' THEN 'NO ACTION'
        WHEN 'r' THEN 'RESTRICT'
        WHEN 'c' THEN 'CASCADE'
        WHEN 'n' THEN 'SET NULL'
        WHEN 'd' THEN 'SET DEFAULT'
        ELSE 'NO ACTION'
      END;

    -- Ensure parent(id) exists (safety net)
    IF NOT EXISTS (
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = r.parent_schema
        AND table_name   = r.parent_table
        AND column_name  = 'id'
    ) THEN
      RAISE NOTICE 'Skipping %, parent %.% has no column id', r.fk_name, r.parent_schema, r.parent_table;
      CONTINUE;
    END IF;

    -- Drop old FK and recreate against parent(id) using the SAME FK NAME
    EXECUTE format(
      'ALTER TABLE %I.%I DROP CONSTRAINT IF EXISTS %I',
      r.child_schema, r.child_table, r.fk_name
    );

    EXECUTE format(
      'ALTER TABLE %I.%I ADD CONSTRAINT %I FOREIGN KEY(%I) REFERENCES %I.%I(id) ON DELETE %s',
      r.child_schema, r.child_table, r.fk_name, r.child_col, r.parent_schema, r.parent_table, del_action
    );
  END LOOP;
END;
END;
$$ LANGUAGE plpgsql;
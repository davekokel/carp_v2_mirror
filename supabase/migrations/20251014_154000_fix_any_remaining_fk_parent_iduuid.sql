DO $$
DECLARE
  r record;
  parent_has_id boolean;
  pkname text;
BEGIN
  FOR r IN
    SELECT
      c.conname,
      child.relname  AS child_table,
      parent.relname AS parent_table,
      a_child.attname AS child_col,
      a_parent.attname AS parent_col
    FROM pg_constraint c
    JOIN pg_class child                    ON child.oid=c.conrelid
    JOIN pg_namespace nchild               ON nchild.oid=child.relnamespace AND nchild.nspname='public'
    JOIN pg_class parent                   ON parent.oid=c.confrelid
    JOIN pg_namespace nparent              ON nparent.oid=parent.relnamespace AND nparent.nspname='public'
    JOIN LATERAL unnest(c.conkey) i(k)     ON TRUE
    JOIN LATERAL unnest(c.confkey) j(k)    ON TRUE
    JOIN pg_attribute a_child              ON a_child.attrelid=child.oid  AND a_child.attnum=i.k
    JOIN pg_attribute a_parent             ON a_parent.attrelid=parent.oid AND a_parent.attnum=j.k
    WHERE c.contype='f'
      AND a_parent.attname='id_uuid'
  LOOP
    -- 1) ensure parent has id
    SELECT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name=r.parent_table AND column_name='id'
    ) INTO parent_has_id;

    IF NOT parent_has_id THEN
      EXECUTE format('ALTER TABLE public.%I ADD COLUMN id uuid', r.parent_table);
      EXECUTE format('UPDATE public.%I SET id = id_uuid WHERE id IS NULL', r.parent_table);
      EXECUTE format('ALTER TABLE public.%I ALTER COLUMN id SET NOT NULL', r.parent_table);
      EXECUTE format('ALTER TABLE public.%I ALTER COLUMN id SET DEFAULT gen_random_uuid()', r.parent_table);
    END IF;

    -- 2) swap parent PK to (id) if not already
    SELECT c.conname
      INTO pkname
    FROM pg_constraint c
    JOIN pg_class cl ON cl.oid=c.conrelid
    JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
    JOIN LATERAL unnest(c.conkey) k(k) ON TRUE
    JOIN pg_attribute a ON a.attrelid=cl.oid AND a.attnum=k.k
    WHERE c.contype='p' AND cl.relname=r.parent_table AND a.attname='id';

    IF pkname IS NULL THEN
      -- drop current PK (whatever its name) and add PK(id)
      SELECT c.conname INTO pkname
      FROM pg_constraint c
      JOIN pg_class cl ON cl.oid=c.conrelid
      JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
      WHERE c.contype='p' AND cl.relname=r.parent_table;

      IF pkname IS NOT NULL THEN
        EXECUTE format('ALTER TABLE public.%I DROP CONSTRAINT %I', r.parent_table, pkname);
      END IF;

      EXECUTE format('ALTER TABLE public.%I ADD CONSTRAINT %I PRIMARY KEY (id)', r.parent_table, r.parent_table||'_pkey');
    END IF;

    -- 3) drop and recreate the child FK to reference parent(id)
    EXECUTE format('ALTER TABLE public.%I DROP CONSTRAINT IF EXISTS %I', r.child_table, r.conname);
    EXECUTE format(
      'ALTER TABLE public.%I ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES public.%I(id)',
      r.child_table, r.conname, r.child_col, r.parent_table
    );
  END LOOP;
END $$;

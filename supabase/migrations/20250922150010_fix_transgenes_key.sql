-- Ensure public.transgenes exposes a canonical text key: transgene_base_code.

DO $$
DECLARE
  pk_col  text;
  pk_type text;
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='transgenes'
      AND column_name='transgene_base_code'
  ) THEN
    RAISE NOTICE 'transgenes.transgene_base_code already exists';
    RETURN;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='transgenes' AND column_name='code'
  ) THEN
    EXECUTE 'ALTER TABLE public.transgenes RENAME COLUMN "code" TO transgene_base_code';
  ELSIF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='transgenes' AND column_name='name'
  ) THEN
    EXECUTE 'ALTER TABLE public.transgenes RENAME COLUMN "name" TO transgene_base_code';
  ELSE
    SELECT a.attname,
           COALESCE(c.data_type, format_type(a.atttypid, a.atttypmod))
      INTO pk_col, pk_type
    FROM pg_constraint con
    JOIN pg_class t       ON t.oid = con.conrelid
    JOIN pg_namespace n   ON n.oid = t.relnamespace
    JOIN unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE
    JOIN pg_attribute a   ON a.attrelid = t.oid AND a.attnum = k.attnum
    LEFT JOIN information_schema.columns c
           ON c.table_schema = n.nspname AND c.table_name = t.relname AND c.column_name = a.attname
    WHERE n.nspname='public' AND t.relname='transgenes' AND con.contype='p'
    ORDER BY k.ord
    LIMIT 1;

    EXECUTE 'ALTER TABLE public.transgenes ADD COLUMN transgene_base_code text';

    IF pk_col IS NOT NULL THEN
      EXECUTE format('UPDATE public.transgenes SET transgene_base_code = %I::text', pk_col);
    ELSE
      EXECUTE 'CREATE EXTENSION IF NOT EXISTS pgcrypto';
      EXECUTE 'UPDATE public.transgenes SET transgene_base_code = md5(gen_random_uuid()::text)';
    END IF;

    EXECUTE 'ALTER TABLE public.transgenes ALTER COLUMN transgene_base_code SET NOT NULL';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint con
    JOIN pg_class t     ON t.oid = con.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname='public' AND t.relname='transgenes' AND con.contype='p'
  ) THEN
    EXECUTE 'ALTER TABLE public.transgenes ADD CONSTRAINT transgenes_pkey PRIMARY KEY (transgene_base_code)';
  ELSE
    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint con
      JOIN pg_class t     ON t.oid = con.conrelid
      JOIN pg_namespace n ON n.oid = t.relnamespace
      WHERE n.nspname='public' AND t.relname='transgenes' AND con.contype='u'
        AND pg_get_constraintdef(con.oid) LIKE 'UNIQUE (transgene_base_code)'
    ) THEN
      EXECUTE 'ALTER TABLE public.transgenes ADD CONSTRAINT transgenes_transgene_base_code_key UNIQUE (transgene_base_code)';
    END IF;
  END IF;
END$$ LANGUAGE plpgsql;

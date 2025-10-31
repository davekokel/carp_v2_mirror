DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT n.nspname AS schema_name, c.relname AS table_name, t.tgname AS trigger_name
    FROM pg_trigger t
    JOIN pg_proc p      ON p.oid = t.tgfoid
    JOIN pg_class c     ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE NOT t.tgisinternal
      AND (p.proname = 'trg_plasmid_auto_ensure_rna'
           OR pg_get_functiondef(p.oid) ILIKE '%ensure_rna_for_plasmid(%'
           OR pg_get_functiondef(p.oid) ILIKE '%public.rnas%')
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I.%I', r.trigger_name, r.schema_name, r.table_name);
  END LOOP;
END $$;

DROP FUNCTION IF EXISTS public.trg_plasmid_auto_ensure_rna() CASCADE;
DROP FUNCTION IF EXISTS public.ensure_rna_for_plasmid(text,text,text,text,text);
DROP FUNCTION IF EXISTS public.ensure_rna_for_plasmid(text,text,text,text);

CREATE OR REPLACE FUNCTION public.ensure_rna_for_plasmid(
  p_code text,
  p_name text,
  p_created_by text,
  p_notes text
) RETURNS text
LANGUAGE plpgsql AS $$
BEGIN
  RETURN p_code;
END $$;

CREATE OR REPLACE FUNCTION public.ensure_rna_for_plasmid(
  p_code text,
  p_name text,
  p_source_name text,
  p_created_by text,
  p_notes text
) RETURNS text
LANGUAGE plpgsql AS $$
BEGIN
  RETURN p_code;
END $$;

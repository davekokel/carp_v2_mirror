-- Safely remove RNA auto-create triggers and make ensure_rna_for_plasmid() a no-op (functions only; skip aggregates)
DO $$
DECLARE
  r record;
BEGIN
  -- Drop any non-internal triggers whose function body references public.rnas or ensure_rna_for_plasmid
  FOR r IN
    SELECT t.tgname, (p.oid::regprocedure)::text AS regproc, n.nspname, c.relname
    FROM pg_trigger t
    JOIN pg_proc p      ON p.oid = t.tgfoid
    JOIN pg_class c     ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE NOT t.tgisinternal
      AND p.prokind = 'f'
      AND (
        pg_get_functiondef(p.oid) ILIKE '%public.rnas%' OR
        pg_get_functiondef(p.oid) ILIKE '%ensure_rna_for_plasmid(%' OR
        p.proname ILIKE 'trg_plasmid_auto_ensure_rna%'
      )
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I.%I', r.tgname, r.nspname, r.relname);
  END LOOP;

  -- Drop trigger functions by exact signature (functions only)
  FOR r IN
    SELECT (p.oid::regprocedure)::text AS regproc
    FROM pg_proc p
    WHERE p.prokind = 'f'
      AND (
        p.proname ILIKE 'trg_plasmid_auto_ensure_rna%' OR
        pg_get_functiondef(p.oid) ILIKE '%public.rnas%' OR
        pg_get_functiondef(p.oid) ILIKE '%ensure_rna_for_plasmid(%'
      )
  LOOP
    EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.regproc);
  END LOOP;
END $$;

-- Install no-op helpers (overloads) so callers don't break
CREATE OR REPLACE FUNCTION public.ensure_rna_for_plasmid(
  p_code text, p_name text, p_created_by text, p_notes text
) RETURNS text LANGUAGE plpgsql AS $$
BEGIN
  RETURN p_code;
END $$;

CREATE OR REPLACE FUNCTION public.ensure_rna_for_plasmid(
  p_code text, p_name text, p_source_name text, p_created_by text, p_notes text
) RETURNS text LANGUAGE plpgsql AS $$
BEGIN
  RETURN p_code;
END $$;

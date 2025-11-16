BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'S' AND n.nspname = 'public' AND c.relname = 'transgene_allele_global_seq'
  ) THEN
    EXECUTE 'CREATE SEQUENCE public.transgene_allele_global_seq START 1';
  END IF;
END$$;

CREATE OR REPLACE FUNCTION public.upsert_transgene_allele(
  p_base text,
  p_nickname text
)
RETURNS TABLE (
  transgene_base_code text,
  allele_number int,
  allele_name text,
  allele_nickname text
)
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_base text := btrim(p_base);
  v_nick text := NULLIF(btrim(p_nickname), '');
  v_num  int;
  v_name text;
BEGIN
  IF v_base IS NULL OR v_base = '' THEN
    RETURN;
  END IF;

  INSERT INTO public.transgenes(transgene_base_code)
  VALUES (v_base)
  ON CONFLICT DO NOTHING;

  IF v_nick IS NOT NULL THEN
    SELECT ta.transgene_base_code, ta.allele_number, ta.allele_name, ta.allele_nickname
      INTO transgene_base_code, allele_number, allele_name, allele_nickname
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = v_base
      AND lower(ta.allele_nickname) = lower(v_nick)
    LIMIT 1;

    IF FOUND THEN
      RETURN NEXT;
      RETURN;
    END IF;
  END IF;

  LOOP
    v_num := nextval('public.transgene_alledge__hack__'||'seq')::int;
  EXIT WHEN FALSE;
  END LOOP;
EXCEPTION
  WHEN undefined_table THEN
    PERFORM 1;
END;
$fn$;

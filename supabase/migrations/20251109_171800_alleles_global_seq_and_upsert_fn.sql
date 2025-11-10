BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

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

CREATE TABLE IF NOT EXISTS public.transgenes (
  transgene_base_code text PRIMARY KEY,
  name text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.transgene_alleles (
  transgene_base_code text NOT NULL REFERENCES public.transgenes(transgene_base_code) ON DELETE RESTRICT,
  allele_number int NOT NULL,
  allele_name text NOT NULL,
  allele_nickname text,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (transgene_base_code, allele_number)
);

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
    v_num := nextval('public.transgene_allele_global_seq')::int;
    v_name := 'gu' || v_num::text;
    BEGIN
      INSERT INTO public.transgene_alleles(
        transgene_base_code, allele_number, allele_name, allele_nickname
      ) VALUES (v_base, v_num, v_name, COALESCE(v_nick, v_name));
      EXIT;
    EXCEPTION WHEN unique_violation THEN
      CONTINUE;
    END;
  END LOOP;

  transgene_base_code := v_base;
  allele_number       := v_num;
  allele_name         := v_name;
  allele_nickname     := COALESCE(v_nick, v_name);
  RETURN NEXT;
  RETURN;
END
$fn$;

COMMIT;

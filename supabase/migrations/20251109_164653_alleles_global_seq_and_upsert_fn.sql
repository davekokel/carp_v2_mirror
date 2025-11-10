BEGIN;

-- 1) Global sequence (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE c.relkind='S' AND n.nspname='public' AND c.relname='transgene_allele_global_seq'
  ) THEN
    EXECUTE 'CREATE SEQUENCE public.transgene_allele_global_seq START 1';
  END IF;
END$$;

-- 2) Upsert function implementing your rules exactly
--    - allele_nickname is a STRING (no numeric coercion)
--    - reuse allele for same base+nickname
--    - otherwise mint new global allele_number = nextval(seq)
--    - allele_name = ''||'gu' || allele_number
--    - default nickname to allele_name if CSV left it blank
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
  IF v_base IS NULL OR v_base='' THEN
    RETURN;
  END IF;

  -- ensure base exists
  INSERT INTO public.transgenes(transgene_base_code)
  VALUES (v_base)
  ON CONFLICT DO NOTHING;

  -- 1) Reuse if an allele already exists for this base+nickname (case-insensitive)
  IF v_nick IS NOT NULL THEN
    SELECT ta.allele_number, ta.allele_name, ta.allele_nickname
      INTO v_num, v_name, v_nick
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = v_base
      AND lower(ta.allele_nickname) = lower(v_nick)
    LIMIT 1;

    IF FOUND THEN
      transgene_base_code := v_base;
      allele_number       := v_num;
      allele_name         := v_name;
      allele_nickname     := v_nick;
      RETURN NEXT;
      RETURN;
    END IF;
  END IF;

  -- 2) Mint a NEW allele using a GLOBAL number; loop to avoid rare collision
  LOOP
    v_num := nextval('public.transgene_allele_global_seq')::int;
    v_name := 'gu' || v_num::text;
    BEGIN
      INSERT INTO public.transgene_alleles(
        transgene_base_code, allele_number, allele_name, allele_nickname
      )
      VALUES (v_base, v_num, v_name, COALESCE(v_nick, v_name));
      EXIT;
    EXCEPTION WHEN unique_violation THEN
      -- (highly unlikely unless someone manually inserted that number)
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

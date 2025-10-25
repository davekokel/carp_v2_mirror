BEGIN;

-- 0) Clean up legacy overloads that may shadow the new bodies (safe if absent)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_proc
    WHERE proname='ensure_allele_from_csv'
      AND pronamespace='public'::regnamespace
      AND pg_get_function_identity_arguments(oid) IN ('text, text')
  ) THEN
    -- drop legacy version with ambiguous ON CONFLICT, if any
    EXECUTE 'DROP FUNCTION public.ensure_allele_from_csv(text, text)';
  END IF;

  IF EXISTS (
    SELECT 1 FROM pg_proc
    WHERE proname='upsert_fish_allele_from_csv'
      AND pronamespace='public'::regnamespace
      AND pg_get_function_identity_arguments(oid) IN ('uuid, text, text')
  ) THEN
    EXECUTE 'DROP FUNCTION public.upsert_fish_allele_from_csv(uuid, text, text)';
  END IF;
END $$;

-- 1) Named unique constraint for deterministic conflict target
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    WHERE t.relname = 'transgene_alleles'
      AND c.conname = 'uq_transgene_alleles_base_num'
  ) THEN
    ALTER TABLE public.transgene_alleles
      ADD CONSTRAINT uq_transgene_alleles_base_num
      UNIQUE (transgene_base_code, allele_number);
  END IF;
END $$;

-- 2) Deterministic allele ensure; nickname is a STRING; global guN
CREATE OR REPLACE FUNCTION public.ensure_allele_from_csv(
  p_base_code   text,
  p_allele_nick text
)
RETURNS TABLE(
  out_allele_number   int,
  out_allele_name     text,
  out_allele_nickname text
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_num  int;
  v_nick text := NULLIF(p_allele_nick, '');
BEGIN
  -- (a) reuse by registry (exact per-base nickname)
  IF v_nick IS NOT NULL THEN
    SELECT r.allele_number
      INTO v_num
      FROM public.transgene_allele_registry r
     WHERE r.transgene_base_code = p_base_code
       AND r.allele_nickname     = v_nick
     LIMIT 1;
  END IF;

  -- (b) reuse existing allele row with same nickname for this base
  IF v_num IS NULL THEN
    SELECT ta.allele_number
      INTO v_num
      FROM public.transgene_alleles ta
     WHERE ta.transgene_base_code = p_base_code
       AND COALESCE(ta.allele_nickname,'') = COALESCE(v_nick,'')
     LIMIT 1;
  END IF;

  -- (c) otherwise mint next GLOBAL guN
  IF v_num IS NULL THEN
    SELECT COALESCE(MAX(ta.allele_number), 0) + 1
      INTO v_num
      FROM public.transgene_alleles ta;
  END IF;

  -- (d) upsert parent row — target the named constraint to avoid ambiguity
  INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, allele_name, allele_nickname)
  VALUES (p_base_code, v_num, 'gu'||v_num::text, v_nick)
  ON CONFLICT ON CONSTRAINT uq_transgene_alleles_base_num DO UPDATE
    SET allele_nickname = COALESCE(EXCLUDED.allele_nickname, public.transgene_alleles.allele_nickname);

  out_allele_number   := v_num;
  out_allele_name     := 'gu'||v_num::text;
  out_allele_nickname := COALESCE(v_nick, 'gu'||v_num::text);
  RETURN NEXT;
END
$$;

-- 3) Wrapper used by the Streamlit page: link allele to fish
CREATE OR REPLACE FUNCTION public.upsert_fish_allele_from_csv(
  p_fish_id     uuid,
  p_base_code   text,
  p_allele_nick text
)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  a RECORD;
BEGIN
  SELECT * INTO a
  FROM public.ensure_allele_from_csv(p_base_code, p_allele_nick);

  INSERT INTO public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number)
  VALUES (p_fish_id, p_base_code, a.out_allele_number)
  ON CONFLICT (fish_id, transgene_base_code)
  DO UPDATE SET allele_number = EXCLUDED.allele_number;
END
$$;

COMMIT;

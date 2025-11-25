BEGIN;

-- 1) Global sequence for allele_number, if not already present
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_class
    WHERE relkind = 'S'
      AND relname = 'transgene_alleles_allele_number_seq'
  ) THEN
    CREATE SEQUENCE public.transgene_alleles_allele_number_seq;
  END IF;
END $$;

-- 2) Align sequence with existing max allele_number
DO $$
DECLARE
  v_max int;
BEGIN
  SELECT max(allele_number) INTO v_max FROM public.transgene_alleles;
  IF v_max IS NULL THEN
    v_max := 0;
  END IF;
  PERFORM setval('public.transgene_alleles_allele_number_seq', v_max, true);
END $$;

-- 3) Enforce global uniqueness of allele_number
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM   pg_constraint
    WHERE  conrelid = 'public.transgene_alleles'::regclass
      AND  conname  = 'transgene_alleles_allele_number_unique'
  ) THEN
    ALTER TABLE public.transgene_alleles
      ADD CONSTRAINT transgene_alleles_allele_number_unique
      UNIQUE (allele_number);
  END IF;
END $$;

-- 4) Optional uniqueness of (base_code, allele_nickname) where nickname present
CREATE UNIQUE INDEX IF NOT EXISTS uniq_transgene_alleles_nickname
  ON public.transgene_alleles(transgene_base_code, allele_nickname)
  WHERE allele_nickname IS NOT NULL;

-- 5) Canonical allocator function with auto-mint of transgenes
CREATE OR REPLACE FUNCTION public.ensure_transgene_allele(
  p_base_code       text,
  p_allele_nickname text
)
RETURNS TABLE (
  transgene_base_code text,
  allele_number       integer,
  allele_name         text,
  allele_nickname     text
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_base  text;
  v_nick  text;
  v_row   public.transgene_alleles%ROWTYPE;
  v_dummy int;
  v_name  text;
BEGIN
  -- Normalize base_code
  v_base := trim(p_base_code);
  IF v_base IS NULL OR v_base = '' THEN
    RAISE EXCEPTION 'ensure_transgene_allele: base_code must not be empty';
  END IF;

  -- 5a) Ensure transgene row exists. If not, mint from constructs if possible.
  SELECT 1 INTO v_dummy
  FROM public.transgenes t
  WHERE t.transgene_base_code = v_base;

  IF NOT FOUND THEN
    -- Try plasmids
    SELECT p.name
    INTO v_name
    FROM public.plasmids p
    WHERE p.code = v_base
    LIMIT 1;

    IF FOUND THEN
      INSERT INTO public.transgenes (transgene_base_code, transgene_name, description, created_at)
      VALUES (v_base, v_name, NULL, now());
    ELSE
      -- Try RNAs
      SELECT r.name
      INTO v_name
      FROM public.rnas r
      WHERE r.rna_base_code = v_base
      LIMIT 1;

      IF FOUND THEN
        INSERT INTO public.transgenes (transgene_base_code, transgene_name, description, created_at)
        VALUES (v_base, v_name, NULL, now());
      ELSE
        RAISE EXCEPTION
          'ensure_transgene_allele: base_code=% not present in transgenes or constructs',
          v_base;
      END IF;
    END IF;
  END IF;

  -- Normalize nickname (treat 'nan', 'na', 'none' as empty)
  v_nick := trim(p_allele_nickname);
  IF v_nick IS NULL OR v_nick = '' OR lower(v_nick) IN ('nan', 'na', 'none') THEN
    v_nick := NULL;
  END IF;

  -- 5b) If nickname present, try to reuse existing allele (base_code, nickname)
  IF v_nick IS NOT NULL THEN
    SELECT ta.*
    INTO v_row
    FROM public.transgene_alleles AS ta
    WHERE ta.transgene_base_code = v_base
      AND ta.allele_nickname     = v_nick
    LIMIT 1;

    IF FOUND THEN
      transgene_base_code := v_row.transgene_base_code;
      allele_number       := v_row.allele_number;
      allele_name         := v_row.allele_name;
      allele_nickname     := v_row.allele_nickname;
      RETURN;
    END IF;
  END IF;

  -- 5c) Mint new allele_number from global sequence
  SELECT nextval('public.transgene_alleles_allele_number_seq')::int
  INTO allele_number;

  allele_name := 'gu' || allele_number;

  IF v_nick IS NULL THEN
    allele_nickname := allele_name;
  ELSE
    allele_nickname := v_nick;
  END IF;

  INSERT INTO public.transgene_alleles (
    transgene_base_code,
    allele_number,
    allele_name,
    allele_nickname,
    created_at
  )
  VALUES (
    v_base,
    allele_number,
    allele_name,
    allele_nickname,
    now()
  );

  transgene_base_code := v_base;
  RETURN;
END;
$$;

COMMIT;

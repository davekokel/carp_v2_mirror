-- Ensure supporting indexes exist (no-ops if already there)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='uq_transgene_alleles_nickname_per_base'
  ) THEN
    CREATE UNIQUE INDEX uq_transgene_alleles_nickname_per_base
      ON public.transgene_alleles(transgene_base_code, allele_nickname)
      WHERE allele_nickname IS NOT NULL;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='uq_transgene_alleles_global_number'
  ) THEN
    CREATE UNIQUE INDEX uq_transgene_alleles_global_number
      ON public.transgene_alleles(allele_number);
  END IF;
END
$$;

DROP FUNCTION IF EXISTS public.upsert_transgene_allele(text, text);

CREATE FUNCTION public.upsert_transgene_allele(
  p_base text,
  p_nickname_in text
)
RETURNS TABLE(transgene_base_code text, allele_number int, allele_name text, allele_nickname text)
LANGUAGE plpgsql
AS $$
DECLARE
  v_nickname text := NULLIF(btrim(p_nickname_in), '');
  v_num int;
  v_name text;
  v_base text;
  v_anum int;
  v_aname text;
  v_anick text;
BEGIN
  -- If nickname provided and (base, nickname) exists, return it
  IF v_nickname IS NOT NULL THEN
    SELECT ta.transgene_base_code, ta.allele_number, ta.allele_name, ta.allele_nickname
      INTO v_base, v_anum, v_aname, v_anick
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = p_base
      AND ta.allele_nickname = v_nickname
    LIMIT 1;

    IF v_base IS NOT NULL THEN
      transgene_base_code := v_base;
      allele_number       := v_anum;
      allele_name         := v_aname;
      allele_nickname     := v_anick;
      RETURN NEXT;
      RETURN;
    END IF;
  END IF;

  -- Otherwise mint the next global allele_number and insert
  LOOP
    BEGIN
      v_num  := nextval('public.transgene_allele_number_seq')::int;
      v_name := 'gu' || v_num::text;

      INSERT INTO public.transgene_alleles(
        transgene_base_code, allele_number, allele_name, allele_nickname
      )
      VALUES (
        p_base, v_num, v_name, COALESCE(v_nickname, v_name)
      )
      RETURNING
        public.transgene_alleles.transgene_base_code,
        public.transgene_alleles.allele_number,
        public.transgene_alleles.allele_name,
        public.transgene_alleles.allele_nickname
      INTO v_base, v_anum, v_aname, v_anick;

      transgene_base_code := v_base;
      allele_number       := v_anum;
      allele_name         := v_aname;
      allele_nickname     := v_anick;
      RETURN NEXT;
      RETURN;

    EXCEPTION
      WHEN unique_violation THEN
        -- race on allele_number: try again
        CONTINUE;
    END;
  END LOOP;
END
$$;

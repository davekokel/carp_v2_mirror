DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE connamespace='public'::regnamespace
      AND conrelid='public.fish_transgene_alleles'::regclass
      AND conname='con_fta_fish_uuid_base'
  ) THEN
    IF EXISTS (
      SELECT 1 FROM pg_class WHERE relnamespace='public'::regnamespace AND relname='uq_fta_fish_uuid_base'
    ) THEN
      ALTER TABLE public.fish_transgene_alleles
        ADD CONSTRAINT con_fta_fish_uuid_base
        UNIQUE USING INDEX uq_fta_fish_uuid_base;
    ELSE
      ALTER TABLE public.fish_transgene_alleles
        ADD CONSTRAINT con_fta_fish_uuid_base
        UNIQUE (fish_uuid, transgene_base_code);
    END IF;
  END IF;
END$$;

DROP FUNCTION IF EXISTS public.upsert_transgene_allele(text, text);
CREATE FUNCTION public.upsert_transgene_allele(
  p_base text,
  p_nickname_in text
)
RETURNS TABLE(out_base text, out_num int, out_name text, out_nick text)
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_nickname text := NULLIF(btrim(p_nickname_in), '');
  v_num int;
  v_name text;
  v_base text;
  v_anum int;
  v_aname text;
  v_anick text;
BEGIN
  INSERT INTO public.transgenes(transgene_base_code)
  VALUES (p_base)
  ON CONFLICT ON CONSTRAINT transgenes_pkey DO NOTHING;

  IF v_nickname IS NOT NULL THEN
    SELECT ta.transgene_base_code, ta.allele_number, ta.allele_name, ta.allele_nickname
      INTO v_base, v_anum, v_aname, v_anick
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = p_base
      AND ta.allele_nickname = v_nickname
    LIMIT 1;

    IF v_base IS NOT NULL THEN
      out_base := v_base;
      out_num  := v_anum;
      out_name := v_aname;
      out_nick := v_anick;
      RETURN NEXT;
      RETURN;
    END IF;
  END IF;

  LOOP
    BEGIN
      v_num  := nextval('public.transgene_allele_number_seq')::int;
      v_name := 'gu' || v_num::text;

      INSERT INTO public.transgene_alleles(
        transgene_base_code, allele_number, allele_name, allele_nickname
      )
      VALUES (p_base, v_num, v_name, COALESCE(v_nickname, v_name))
      RETURNING
        public.transgene_alleles.transgene_base_code,
        public.transgene_alleles.allele_number,
        public.transgene_alleles.allele_name,
        public.transgene_alleles.allele_nickname
      INTO v_base, v_anum, v_aname, v_anick;

      out_base := v_base;
      out_num  := v_anum;
      out_name := v_aname;
      out_nick := v_anick;
      RETURN NEXT;
      RETURN;
    EXCEPTION WHEN unique_violation THEN
      CONTINUE;
    END;
  END LOOP;
END
$fn$;

DROP FUNCTION IF EXISTS public.upsert_fish_allele_from_csv(uuid, text, text);
CREATE FUNCTION public.upsert_fish_allele_from_csv(
  p_fish_uuid uuid,
  p_base_code text,
  p_allele_nickname text
)
RETURNS TABLE(fish_uuid uuid, transgene_base_code text, allele_number int)
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_allele_number int;
  v_fu uuid;
  v_base text;
  v_anum int;
BEGIN
  SELECT ta.allele_number
    INTO v_allele_number
  FROM public.transgene_alleles ta
  WHERE ta.transgene_base_code = p_base_code
    AND ta.allele_nickname = NULLIF(btrim(p_allele_nickname), '')
  LIMIT 1;

  IF v_allele_number IS NULL THEN
    SELECT u.out_num
      INTO v_allele_number
    FROM public.upsert_transgene_allele(p_base_code, p_allele_nickname) AS u;
  END IF;

  INSERT INTO public.fish_transgene_alleles (fish_uuid, transgene_base_code, allele_number)
  VALUES (p_fish_uuid, p_base_code, v_allele_number)
  ON CONFLICT ON CONSTRAINT con_fta_fish_uuid_base
  DO UPDATE SET allele_number = EXCLUDED.allele_number
  RETURNING public.fish_transgene_alleles.fish_uuid,
            public.fish_transgene_alleles.transgene_base_code,
            public.fish_transgene_alleles.allele_number
  INTO v_fu, v_base, v_anum;

  fish_uuid := v_fu;
  transgene_base_code := v_base;
  allele_number := v_anum;
  RETURN NEXT;
END
$fn$;

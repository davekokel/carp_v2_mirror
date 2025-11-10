BEGIN;

CREATE SEQUENCE IF NOT EXISTS public."transgene_allele_global";

DROP FUNCTION IF EXISTS public.upsert_transgene_allele(text,text);

CREATE FUNCTION public.upsert_transgene_allele(p_base text, p_nickname text)
RETURNS TABLE(transgene_base_code text, allele_number int, allele_name text, allele_nickname text)
LANGUAGE plpgsql
AS $$
DECLARE
  v_base text := NULLIF(btrim(p_base), '');
  v_nick text := NULLIF(btrim(p_nickname), '');
  v_row  public.transgene_alleles%ROWTYPE;
  v_new  int;
  v_gu   text;
BEGIN
  IF v_base IS NULL THEN
    RETURN;
  END IF;

  IF v_nick IS NOT NULL THEN
    IF lower(v_nick) IN ('unknown','unk','n/a','na','none','?','-') THEN
      v_nick := NULL;
    ELSIF v_nick ~ '^\d+(?:\.0+)?$' THEN
      v_nick := NULL;
    END IF;
  END IF;

  INSERT INTO public.transgenes(transgene_base_code) VALUES (v_base)
  ON CONFLICT DO NOTHING;

  IF v_nick IS NULL THEN
    SELECT * INTO v_row
    FROM public.transgene_alleles
    WHERE transgene_base_code = v_base
    ORDER BY allele_number
    LIMIT 1;

    IF FOUND THEN
      transgene_base_code := v_row.transgene_base_code;
      allele_number       := v_row.allele_number;
      allele_name         := COALESCE(v_row.allele_name, 'gu'||v_row.allele_number);
      allele_nickname     := COALESCE(v_row.allele_nickname, 'gu'||v_row.allele_number);
      RETURN NEXT;
      RETURN;
    END IF;
  ELSE
    SELECT * INTO v_row
    FROM public.transgene_alleles
    WHERE transgene_base_code = v_base
      AND lower(allele_nickname) = lower(v_nick)
    LIMIT 1;

    IF FOUND THEN
      transgene_base_code := v_row.transgene_base_code;
      allele_number       := v_row.allele_number;
      allele_name         := COALESCE(v_row.allele_name, 'gu'||v_row.allele_number);
      allele_nickname     := v_row.allele_nickname;
      RETURN NEXT;
      RETURN;
    END IF;
  END IF;

  LOOP
    v_new := nextval('public."transgene_allele_global"')::int;
    v_gu  := 'gu'||v_new;
    BEGIN
      INSERT INTO public.transgene_alleles
        (transgene_base_code, allele_number, allele_name, allele_nickname)
      VALUES
        (v_base, v_new, v_gu, COALESCE(v_nick, v_gu))
      ON CONFLICT DO NOTHING;

      SELECT * INTO v_row
      FROM public.transgene_alleles
      WHERE transgene_base_code = v_base AND allele_number = v_new
      LIMIT 1;

      IF FOUND THEN
        transgene_base_code := v_row.transgene_base_code;
        allele_number       := v_row.allele_number;
        allele_name         := v_row.allele_name;
        allele_nickname     := v_row.allele_nickname;
        RETURN NEXT;
        RETURN;
      END IF;
    EXCEPTION WHEN unique_violation THEN
    END;
  END LOOP;
END;
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_transgene_alleles_base_nickname
ON public.transgene_alleles (transgene_base_code, lower(allele_nickname))
WHERE allele_nickname IS NOT NULL;

COMMIT;

BEGIN;

-- Replace function so it doesn't depend on a 'name' column existing on transgenes
CREATE OR REPLACE FUNCTION public.upsert_transgene_allele(
  p_base_code      text,
  p_allele_nick_in text
)
RETURNS TABLE (
  transgene_base_code text,
  allele_number       bigint,
  allele_name         text
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_base   text;
  v_nick   text;
  v_num    bigint;
  v_name   text;
BEGIN
  v_base := btrim(p_base_code);
  IF v_base IS NULL OR v_base = '' THEN
    RAISE EXCEPTION 'transgene base_code is required';
  END IF;

  -- Ensure transgene exists (insert minimal column set)
  IF NOT EXISTS (SELECT 1 FROM public.transgenes t WHERE t.transgene_base_code = v_base) THEN
    INSERT INTO public.transgenes (transgene_base_code) VALUES (v_base);
  END IF;

  -- Normalize nickname; keep original casing if provided
  v_nick := CASE
              WHEN p_allele_nick_in IS NULL THEN NULL
              ELSE NULLIF(btrim(p_allele_nick_in), '')
            END;

  -- Reuse existing allele by nickname within this base_code (idempotent)
  IF v_nick IS NOT NULL THEN
    SELECT ta.allele_number, ta.allele_name
      INTO v_num, v_name
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = v_base
      AND lower(btrim(ta.allele_nickname)) = lower(btrim(v_nick))
    LIMIT 1;

    IF v_num IS NOT NULL THEN
      transgene_base_code := v_base; allele_number := v_num; allele_name := v_name; RETURN;
    END IF;
  END IF;

  -- Mint new global allele number
  v_num := nextval('public.seq_global_allele_number');
  v_name := 'gu' || v_num::text;

  INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, allele_name, allele_nickname)
  VALUES (v_base, v_num, v_name, COALESCE(v_nick, v_name));

  transgene_base_code := v_base; allele_number := v_num; allele_name := v_name; RETURN;
END
$$;

COMMIT;

BEGIN;

-- Drop the old function so we can recreate with the correct OUT signature
DROP FUNCTION IF EXISTS public.upsert_transgene_allele(text, text);

CREATE OR REPLACE FUNCTION public.upsert_transgene_allele(
  p_transgene_base_code text,
  p_allele_nickname     text
)
RETURNS TABLE (
  transgene_base_code text,
  allele_number       bigint,
  allele_name         text
) AS $$
DECLARE
  v_base text := btrim(p_transgene_base_code);
  v_nick text := NULLIF(btrim(p_allele_nickname), '');
  v_num  bigint;
  v_name text;
BEGIN
  IF v_base IS NULL OR v_base = '' THEN
    -- Nothing to do; return no row
    RETURN;
  END IF;

  -- Ensure a transgene row exists (only the base code is required)
  IF NOT EXISTS (
      SELECT 1 FROM public.transgenes t WHERE t.transgene_base_code = v_base
  ) THEN
    INSERT INTO public.transgenes (transgene_base_code) VALUES (v_base)
    ON CONFLICT (transgene_base_code) DO NOTHING;
  END IF;

  -- Reuse existing allele if nickname is provided and matches within the same base
  IF v_nick IS NOT NULL THEN
    SELECT ta.allele_number, ta.allele_name
      INTO v_num, v_name
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = v_base
      AND lower(btrim(ta.allele_nickname)) = lower(btrim(v_nick))
    LIMIT 1;

    IF v_num IS NOT NULL THEN
      transgene_base_code := v_base;
      allele_number       := v_num;
      allele_name         := v_name;
      RETURN NEXT;
      RETURN;
    END IF;
  END IF;

  -- Mint a new global allele number: prefer sequence, fall back to MAX+1
  BEGIN
    v_num := nextval('public.seq_global_allele_number');
  EXCEPTION
    WHEN undefined_table OR undefined_object THEN
      SELECT COALESCE(MAX(allele_number), 0) + 1 INTO v_num FROM public.transgene_alleles;
  END;

  v_name := 'gu' || v_num::text;

  INSERT INTO public.transgene_alleles (
    transgene_base_code, allele_number, allele_name, allele_nickname
  ) VALUES (
    v_base, v_num, v_name, COALESCE(v_nick, v_name)
  )
  ON CONFLICT DO NOTHING;

  transgene_base_code := v_base;
  allele_number       := v_num;
  allele_name         := v_name;
  RETURN NEXT;
END
$$ LANGUAGE plpgsql;

COMMIT;

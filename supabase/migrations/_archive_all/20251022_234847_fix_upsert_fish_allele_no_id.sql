-- Replace helper: insert into fish_transgene_alleles without a synthetic id column.
DROP FUNCTION IF EXISTS public.upsert_fish_allele_from_csv(uuid, text, text);

CREATE FUNCTION public.upsert_fish_allele_from_csv(
  v_fish_id uuid,
  v_base_code text,
  v_allele_nickname text
) RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  v_num int;
  v_nick_final text;
BEGIN
  IF coalesce(v_base_code,'') = '' THEN
    RETURN;
  END IF;

  -- Reuse existing mapping if present
  SELECT r.allele_number
    INTO v_num
    FROM public.transgene_allele_registry r
   WHERE r.transgene_base_code = v_base_code
     AND coalesce(r.allele_nickname,'') = coalesce(v_allele_nickname,'')
   LIMIT 1;

  -- Otherwise mint next global allele_number; default nickname to guN when blank
  IF v_num IS NULL THEN
    SELECT coalesce(MAX(allele_number),0)+1 INTO v_num
      FROM public.transgene_allele_registry;

    v_nick_final := coalesce(NULLIF(v_allele_nickname,''), 'gu' || v_num::text);

    INSERT INTO public.transgene_allele_registry (transgene_base_code, allele_number, allele_nickname, created_at)
    VALUES (v_base_code, v_num, v_nick_final, now())
    ON CONFLICT DO NOTHING;
  END IF;

  -- Ensure the allele exists in transgene_alleles
  INSERT INTO public.transgene_alleles (transgene_base_code, allele_number)
  VALUES (v_base_code, v_num)
  ON CONFLICT DO NOTHING;

  -- Link fish ↔ allele (composite key, no id column here)
  INSERT INTO public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number)
  VALUES (v_fish_id, v_base_code, v_num)
  ON CONFLICT DO NOTHING;

END;
$$;

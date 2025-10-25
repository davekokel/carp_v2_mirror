-- Fix allele helper and rebuild v_fish_standard_clean without changing column names/order.

-- 1) Replace helper: drop old signature then create void-returning version
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

  SELECT r.allele_number
    INTO v_num
    FROM public.transgene_allele_registry r
   WHERE r.transgene_base_code = v_base_code
     AND coalesce(r.allele_nickname,'') = coalesce(v_allele_nickname,'')
   LIMIT 1;

  IF v_num IS NULL THEN
    SELECT coalesce(MAX(allele_number),0)+1 INTO v_num
      FROM public.transgene_allele_registry;

    v_nick_final := coalesce(NULLIF(v_allele_nickname,''), 'gu' || v_num::text);

    INSERT INTO public.transgene_allele_registry (transgene_base_code, allele_number, allele_nickname, created_at)
    VALUES (v_base_code, v_num, v_nick_final, now())
    ON CONFLICT DO NOTHING;
  END IF;

  INSERT INTO public.transgene_alleles (transgene_base_code, allele_number)
  VALUES (v_base_code, v_num)
  ON CONFLICT DO NOTHING;

  INSERT INTO public.fish_transgene_alleles (id, fish_id, transgene_base_code, allele_number)
  VALUES (gen_random_uuid(), v_fish_id, v_base_code, v_num)
  ON CONFLICT DO NOTHING;
END;
$$;

-- 2) Recreate v_fish_standard_clean but keep existing column names/order.
-- First column must remain "fish_code" to avoid rename errors; do not add/remove columns.
CREATE OR REPLACE VIEW public.v_fish_standard_clean
AS
SELECT
  f.fish_code,                              -- keep as first column (unchanged)
  f.name,
  f.nickname,
  f.genetic_background,
  f.line_building_stage,
  f.date_birth                          AS birth_date,
  f.created_at                          AS created_time,
  f.created_by,
  fta.transgene_base_code,
  fta.allele_number,
  r.allele_nickname,
  ('gu' || fta.allele_number::text)     AS allele_name,              -- derived
  ('Tg('||fta.transgene_base_code||')'||coalesce(r.allele_nickname,''))             AS transgene_pretty_nickname,
  ('Tg('||fta.transgene_base_code||')'||('gu'||fta.allele_number::text))            AS transgene_pretty_name,
  (
    SELECT string_agg('Tg('||fta2.transgene_base_code||')'||('gu'||fta2.allele_number::text),
                      '; ' ORDER BY f. fish_code, fta2.transgene_base_code, fta2.allele_number)
  ) AS genotype
FROM public.fish f
LEFT JOIN public.fish_transgene_alleles fta
       ON fta.fish_id = f.id
LEFT JOIN public.transgene_allele_registry r
       ON r.transgene_base_code = fta.transgene_base_code
      AND r.allele_number       = fta.allele_number;

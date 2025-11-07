BEGIN;

CREATE SCHEMA IF NOT EXISTS raw;

-- Staging table you can reload anytime
CREATE TABLE IF NOT EXISTS raw.fish_alleles_upload (
  fish_code             text,
  transgene_base_code   text,
  allele_nickname       text,
  zygosity              text
);

-- Processor: idempotent; uses upsert_transgene_allele()
CREATE OR REPLACE FUNCTION public.process_fish_alleles_upload(p_by text)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  r record;
  v_fish_id uuid;
  v_up  record;
  v_zyg text;
BEGIN
  FOR r IN
    SELECT
      btrim(NULLIF(fish_code,''))           AS fish_code,
      btrim(NULLIF(transgene_base_code,'')) AS base_code,
      NULLIF(allele_nickname,'')            AS allele_nick_raw,
      NULLIF(zygosity,'')                   AS zyg_raw
    FROM raw.fish_alleles_upload
  LOOP
    IF r.fish_code IS NULL OR r.base_code IS NULL THEN
      CONTINUE;
    END IF;

    -- resolve fish_id from fish_code
    SELECT id INTO v_fish_id
    FROM public.fish
    WHERE fish_code = r.fish_code
    LIMIT 1;

    IF v_fish_id IS NULL THEN
      CONTINUE;
    END IF;

    -- normalize zygosity to het/hom/unk
    v_zyg := CASE
               WHEN r.zyg_raw IS NULL THEN NULL
               WHEN lower(btrim(r.zyg_raw)) IN ('het','hetero','heterozygous','h') THEN 'het'
               WHEN lower(btrim(r.zyg_raw)) IN ('hom','homo','homozygous') THEN 'hom'
               WHEN lower(btrim(r.zyg_raw)) IN ('unk','unknown','?','na','n/a','none','') THEN 'unk'
               ELSE 'unk'
             END;

    -- upsert allele (nickname kept as string; blank → defaults to guN)
    SELECT * INTO v_up
    FROM public.upsert_transgene_allele(r.base_code, r.allele_nick_raw);

    -- link fish → allele (upsert zygosity)
    INSERT INTO public.join_fish_transgene_alleles (fish_id, transgene_base_code, allele_number, zygosity)
    VALUES (v_fish_id, v_up.transgene_base_code, v_up.allele_number, v_zyg)
    ON CONFLICT (fish_id, transgene_base_code, allele_number) DO UPDATE
      SET zygosity = COALESCE(EXCLUDED.zygosity, public.join_fish_transgene_alleles.zygosity);
  END LOOP;
END
$$;

COMMIT;

BEGIN;

CREATE OR REPLACE VIEW public.v11_fish_instance_star_enriched AS
SELECT
  fis.*,

  -- # transgenes: how many Tg(PDQM-###) entries
  COALESCE(
    NULLIF(fis.genotype_basecode_code, '') IS NULL,
    FALSE
  )::int AS _dummy,  -- just to keep expression order happy

  CASE
    WHEN fis.genotype_basecode_code IS NULL
      OR btrim(fis.genotype_basecode_code) = '' THEN 0
    ELSE array_length(
           regexp_split_to_array(
             fis.genotype_basecode_code,
             '\s*;\s*'
           ),
           1
         )
  END AS n_transgenes,

  -- # fluors: how many distinct fluor names in fluor_codes
  CASE
    WHEN fis.fluor_codes IS NULL
      OR btrim(fis.fluor_codes) = '' THEN 0
    ELSE array_length(
           regexp_split_to_array(
             fis.fluor_codes,
             '\s*,\s*'
           ),
           1
         )
  END AS n_fluors

FROM public.v11_fish_instance_star fis;

COMMIT;

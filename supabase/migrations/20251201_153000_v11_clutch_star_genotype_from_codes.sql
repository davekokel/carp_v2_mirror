BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_star;

CREATE VIEW public.v11_clutch_star AS
WITH imaging AS (
  SELECT
    v.clutch_id,
    v.clutch_code,
    v.clutch_date,
    v.estimated_egg_count,
    COUNT(DISTINCT v.slot_id) AS n_imaging_slots,
    COUNT(v.roi_id)           AS n_rois,
    STRING_AGG(
      DISTINCT v.fish_genotype_pretty,
      ' | ' ORDER BY v.fish_genotype_pretty
    ) AS roi_genotype_pretty
  FROM public.v11_imaging_roi_star v
  GROUP BY
    v.clutch_id,
    v.clutch_code,
    v.clutch_date,
    v.estimated_egg_count
),
exploded AS (
  -- turn base/allele CSV strings into parallel arrays
  SELECT
    c.id::text                                       AS clutch_id,
    c.clutch_code,
    string_to_array(c.genotype_base_codes,   ',')    AS base_arr,
    string_to_array(c.genotype_allele_codes, ',')    AS allele_arr
  FROM public.clutches c
  WHERE c.genotype_base_codes   IS NOT NULL
    AND c.genotype_base_codes   <> ''
    AND c.genotype_allele_codes IS NOT NULL
    AND c.genotype_allele_codes <> ''
),
expanded_codes AS (
  -- index into the arrays so we preserve base[i] ↔ allele[i]
  SELECT
    e.clutch_id,
    e.clutch_code,
    trim(e.base_arr[i])                                      AS base_code,
    trim(regexp_replace(e.allele_arr[i], '\.0+$', ''))       AS allele_nick
  FROM exploded e,
       generate_subscripts(e.base_arr, 1) AS i
  WHERE i <= array_length(e.allele_arr, 1)
),
joined AS (
  -- join exploded codes to transgene_alleles using normalized base_code and allele_nick
  SELECT
    ec.clutch_id,
    ec.clutch_code,
    ta.transgene_base_code,
    ta.allele_number,
    CASE
      WHEN ta.allele_name IS NOT NULL AND ta.allele_name <> ''
        THEN ta.allele_name
      WHEN ta.allele_nickname IS NOT NULL AND ta.allele_nickname <> ''
        THEN ta.allele_nickname
      ELSE ta.allele_number::text
    END AS allele_token
  FROM expanded_codes ec
  LEFT JOIN public.transgene_alleles ta
    ON upper(replace(ta.transgene_base_code, '-', '')) = upper(replace(ec.base_code, '-', ''))
   AND ta.allele_nickname = ec.allele_nick
),
geno AS (
  -- aggregate back to canonical Tg(base)allele_token per clutch
  SELECT
    clutch_id,
    clutch_code,
    string_agg(
      'Tg(' || transgene_base_code || ')' || allele_token,
      '; ' ORDER BY transgene_base_code, allele_number
    ) AS codes_genotype_pretty
  FROM joined
  WHERE allele_token IS NOT NULL
  GROUP BY clutch_id, clutch_code
),
treats AS (
  SELECT
    jct.clutch_id::text AS clutch_id,
    STRING_AGG(DISTINCT t.treat_code, ', ' ORDER BY t.treat_code) AS treat_codes,
    STRING_AGG(DISTINCT tmf.fluor_codes, ', ' ORDER BY tmf.fluor_codes)   AS treat_fluor_tag,
    STRING_AGG(DISTINCT tmf.fluor_names, ', ' ORDER BY tmf.fluor_names)   AS treat_organelle_fluor
  FROM public.join_clutch_treatments jct
  JOIN public.treatments t
    ON t.id = jct.treatment_id
  JOIN public.treatment_mixes tm
    ON tm.treatment_id = t.id
  LEFT JOIN public.v10_treatment_mix_fluors tmf
    ON tmf.mix_id = tm.id
  GROUP BY jct.clutch_id::text
)
SELECT
  c.id::text             AS clutch_id,
  c.clutch_code,
  c.clutch_date,
  c.estimated_egg_count,
  i.n_imaging_slots,
  i.n_rois,
  c.genotype_base_codes,
  c.genotype_allele_codes,
  CASE
    WHEN i.roi_genotype_pretty IS NOT NULL AND i.roi_genotype_pretty <> ''
      THEN i.roi_genotype_pretty
    ELSE geno.codes_genotype_pretty
  END AS genotype_pretty,
  treats.treat_codes,
  treats.treat_fluor_tag,
  treats.treat_organelle_fluor
FROM public.clutches c
LEFT JOIN imaging i
  ON i.clutch_id = c.id::text
LEFT JOIN geno
  ON geno.clutch_id = c.id::text
LEFT JOIN treats
  ON treats.clutch_id = c.id::text
ORDER BY c.clutch_date, c.clutch_code;

COMMIT;

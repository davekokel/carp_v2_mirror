BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_star;

CREATE VIEW public.v11_clutch_star AS
WITH imaging AS (
    SELECT
      v.clutch_id,
      v.clutch_code,
      v.clutch_date,
      v.estimated_egg_count,
      count(DISTINCT v.slot_id) AS n_imaging_slots,
      count(v.roi_id)           AS n_rois,
      string_agg(
        DISTINCT v.fish_genotype_pretty,
        ' | ' ORDER BY v.fish_genotype_pretty
      ) AS roi_genotype_pretty
    FROM public.v11_imaging_roi_star v
    GROUP BY v.clutch_id, v.clutch_code, v.clutch_date, v.estimated_egg_count
),
exploded AS (
    SELECT
      c.id::text AS clutch_id,
      c.clutch_code,
      string_to_array(c.genotype_base_codes,   ',') AS base_arr,
      string_to_array(c.genotype_allele_codes, ',') AS allele_arr
    FROM public.clutches c
    WHERE
      c.genotype_base_codes   IS NOT NULL AND c.genotype_base_codes   <> ''
      AND
      c.genotype_allele_codes IS NOT NULL AND c.genotype_allele_codes <> ''
),
expanded_codes AS (
    SELECT
      e.clutch_id,
      e.clutch_code,
      TRIM(BOTH FROM e.base_arr[i.i])   AS base_code,
      TRIM(BOTH FROM e.allele_arr[i.i]) AS allele_name
    FROM exploded e,
    LATERAL generate_subscripts(e.base_arr, 1) AS i(i)
    WHERE i.i <= array_length(e.allele_arr, 1)
),
joined AS (
    SELECT
      ec.clutch_id,
      ec.clutch_code,
      ta.transgene_base_code,
      ta.allele_number,
      ta.allele_name AS allele_token
    FROM expanded_codes ec
    LEFT JOIN public.transgene_alleles ta
      ON upper(replace(ta.transgene_base_code, '-', '')) = upper(replace(ec.base_code, '-', ''))
     AND ta.allele_name = ec.allele_name
),
geno AS (
    SELECT
      j.clutch_id,
      j.clutch_code,
      string_agg(
        'Tg(' || j.transgene_base_code || ')' || j.allele_token,
        '; ' ORDER BY j.transgene_base_code, j.allele_number
      ) AS codes_genotype_pretty
    FROM joined j
    WHERE j.allele_token IS NOT NULL
    GROUP BY j.clutch_id, j.clutch_code
),
treats AS (
    SELECT
      jct.clutch_id::text AS clutch_id,
      string_agg(DISTINCT t.treat_code,   ', ' ORDER BY t.treat_code)   AS treat_codes,
      string_agg(DISTINCT tmf.fluor_codes, ', ' ORDER BY tmf.fluor_codes) AS treat_fluor_tag,
      string_agg(DISTINCT tmf.fluor_names, ', ' ORDER BY tmf.fluor_names) AS treat_organelle_fluor
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
  c.id::text         AS clutch_id,
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

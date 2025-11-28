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
      trim(both from e.base_arr[i.i])   AS base_code,
      trim(both from e.allele_arr[i.i]) AS allele_name
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
-- genotype construct → marker rollups via v10_constructs_overview
geno_markers AS (
    SELECT
      ec.clutch_id,
      ec.clutch_code,
      co.fusion_pretty,
      co.organelle_fluors
    FROM expanded_codes ec
    JOIN public.v10_constructs_overview co
      ON upper(replace(co.construct_code, '-', '')) = upper(replace(ec.base_code, '-', ''))
),
geno_rollups AS (
    SELECT
      clutch_id,
      clutch_code,
      string_agg(DISTINCT fusion_pretty, ', ' ORDER BY fusion_pretty)       AS geno_fluor_tag_rollup,
      string_agg(DISTINCT organelle_fluors, ', ' ORDER BY organelle_fluors) AS geno_organelle_rollup
    FROM geno_markers
    WHERE (fusion_pretty IS NOT NULL AND fusion_pretty <> '')
       OR (organelle_fluors IS NOT NULL AND organelle_fluors <> '')
    GROUP BY clutch_id, clutch_code
),
treats AS (
    SELECT
      jct.clutch_id::text AS clutch_id,
      string_agg(DISTINCT t.treat_code,   ', ' ORDER BY t.treat_code)     AS treat_codes,
      string_agg(DISTINCT tmf.fluor_codes, ', ' ORDER BY tmf.fluor_codes) AS treat_fluor_tag_raw,
      string_agg(DISTINCT tmf.fluor_names, ', ' ORDER BY tmf.fluor_names) AS treat_organelle_raw,
      string_agg(DISTINCT c2.base_code,     ', ' ORDER BY c2.base_code)   AS treat_base_codes,
      string_agg(DISTINCT co.fusion_pretty, ', ' ORDER BY co.fusion_pretty) AS treat_fluor_tag_pretty,
      string_agg(DISTINCT co.organelle_fluors, ', ' ORDER BY co.organelle_fluors) AS treat_organelle_pretty
    FROM public.join_clutch_treatments jct
    JOIN public.treatments t
      ON t.id = jct.treatment_id
    JOIN public.treatment_mixes tm
      ON tm.treatment_id = t.id
    LEFT JOIN public.v10_treatment_mix_fluors tmf
      ON tmf.mix_id = tm.id
    LEFT JOIN public.treatment_mix_constructs tmc
      ON tmc.mix_id = tm.id
    LEFT JOIN public.constructs c2
      ON c2.id = tmc.construct_id
    LEFT JOIN public.v10_constructs_overview co
      ON co.construct_code = c2.base_code
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
  treats.treat_fluor_tag_raw      AS treat_fluor_tag,
  treats.treat_organelle_raw      AS treat_organelle_fluor,
  CASE
    WHEN treats.treat_base_codes IS NOT NULL
         AND treats.treat_base_codes <> ''
         AND c.genotype_base_codes IS NOT NULL
         AND c.genotype_base_codes <> ''
      THEN treats.treat_base_codes || ' > ' || c.genotype_base_codes
    WHEN treats.treat_base_codes IS NOT NULL
         AND treats.treat_base_codes <> ''
      THEN treats.treat_base_codes
    ELSE c.genotype_base_codes
  END AS treatments_and_transgenes,
  -- treatment+genotype organelle rollup (organelle-fluor format)
  CASE
    WHEN treats.treat_organelle_pretty IS NOT NULL
         AND treats.treat_organelle_pretty <> ''
         AND gr.geno_organelle_rollup IS NOT NULL
         AND gr.geno_organelle_rollup <> ''
      THEN treats.treat_organelle_pretty || ' > ' || gr.geno_organelle_rollup
    WHEN treats.treat_organelle_pretty IS NOT NULL
         AND treats.treat_organelle_pretty <> ''
      THEN treats.treat_organelle_pretty
    ELSE gr.geno_organelle_rollup
  END AS all_organelle_fluor_rollup,
  -- treatment+genotype fluor::tag(tag_pos) rollup
  CASE
    WHEN treats.treat_fluor_tag_pretty IS NOT NULL
         AND treats.treat_fluor_tag_pretty <> ''
         AND gr.geno_fluor_tag_rollup IS NOT NULL
         AND gr.geno_fluor_tag_rollup <> ''
      THEN treats.treat_fluor_tag_pretty || ' > ' || gr.geno_fluor_tag_rollup
    WHEN treats.treat_fluor_tag_pretty IS NOT NULL
         AND treats.treat_fluor_tag_pretty <> ''
      THEN treats.treat_fluor_tag_pretty
    ELSE gr.geno_fluor_tag_rollup
  END AS all_fluor_tag_rollup
FROM public.clutches c
LEFT JOIN imaging i
  ON i.clutch_id = c.id::text
LEFT JOIN geno
  ON geno.clutch_id = c.id::text
LEFT JOIN geno_rollups gr
  ON gr.clutch_id = c.id::text
LEFT JOIN treats
  ON treats.clutch_id = c.id::text
ORDER BY c.clutch_date, c.clutch_code;

COMMIT;

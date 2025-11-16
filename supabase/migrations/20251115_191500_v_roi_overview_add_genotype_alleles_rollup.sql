BEGIN;

CREATE OR REPLACE VIEW public.v_roi_overview AS
SELECT
  ir.id          AS imaging_roi_id,
  ir.dataset,
  ir.experiment_name,
  ir.fish_label,
  ir.fish_id,
  ir.roi_index,
  ir.roi_name,
  ir.roi_dir,
  ir.data_location,
  ir.mount_row_index_scored,
  ir.mount_id,
  ir.date_experiment,
  ir.date_mount,
  ir.raw_id,

  r.zf_female_genotype,
  r.zf_male_genotype,
  r.additional_plasmids_injected,
  r.additional_mrnas_injected,
  r.additonal_dye_and_chemicals,
  r.female_plasmid_base_code,
  r.female_allele,
  r.male_plasmid_base_code,
  r.male_allele,
  r.additional_plasmids_plasmid_base_code,
  r.additional_mrnas_plasmid_base_code,
  r.additonal_dye_dye_base_code,

  p.plasmid_base_code AS inj_plasmid_base_code,
  NULL::text          AS inj_plasmid_name,
  rn.rna_base_code    AS inj_rna_base_code,
  NULL::text          AS inj_rna_name,
  dy.dye_base_code    AS inj_dye_base_code,
  NULL::text          AS inj_dye_name,

  roll.genotype_codes_group,
  roll.genotype_fusions_rollup,
  roll.allele_names_rollup,
  roll.treatments_codes_group,
  roll.treatments_names_group,
  roll.fluors_rollup,

  -- NEW: canonical Tg(base)allele_name rollup for this fish, appended at the end
  (
    SELECT string_agg(
             'Tg(' || jfta.transgene_base_code || ')' || ta.allele_name,
             '; ' ORDER BY jfta.transgene_base_code, ta.allele_number
           )
    FROM public.join_fish_transgene_alleles jfta
    JOIN public.transgene_alleles ta
      ON ta.transgene_base_code = jfta.transgene_base_code
     AND ta.allele_number       = jfta.allele_number
    WHERE jfta.fish_id = ir.fish_id
  ) AS genotype_alleles_rollup

FROM public.imaging_rois ir
JOIN raw.imaging_rois_raw r
  ON r.id = ir.raw_id
LEFT JOIN public.plasmids p
  ON p.plasmid_base_code = r.additional_plasmids_plasmid_base_code
LEFT JOIN public.rnas rn
  ON rn.rna_base_code = r.additional_mrnas_plasmid_base_code
LEFT JOIN public.dyes dy
  ON dy.dye_base_code = r.additonal_dye_dye_base_code
LEFT JOIN LATERAL (
  SELECT
    (
      SELECT string_agg(DISTINCT code, '; ' ORDER BY code)
      FROM (
        VALUES
          (r.female_plasmid_base_code),
          (r.male_plasmid_base_code),
          (r.additional_plasmids_plasmid_base_code),
          (r.additional_mrnas_plasmid_base_code),
          (r.additonal_dye_dye_base_code),
          (p.plasmid_base_code),
          (rn.rna_base_code),
          (dy.dye_base_code)
      ) AS v(code)
      WHERE code IS NOT NULL AND btrim(code) <> ''
    ) AS genotype_codes_group,

    (
      SELECT string_agg(DISTINCT t, '; ' ORDER BY t)
      FROM regexp_split_to_table(
             coalesce(r.zf_female_genotype,'') || ',' ||
             coalesce(r.zf_male_genotype,''),
             '[,;]'
           ) AS t
      WHERE btrim(t) <> ''
    ) AS genotype_fusions_rollup,

    (
      SELECT string_agg(DISTINCT a, '; ' ORDER BY a)
      FROM (
        VALUES (r.female_allele), (r.male_allele)
      ) AS v(a)
      WHERE a IS NOT NULL AND btrim(a) <> ''
    ) AS allele_names_rollup,

    (
      SELECT string_agg(DISTINCT code, '; ' ORDER BY code)
      FROM (
        VALUES
          (r.additional_plasmids_plasmid_base_code),
          (r.additional_mrnas_plasmid_base_code),
          (r.additonal_dye_dye_base_code),
          (dy.dye_base_code)
      ) AS v(code)
      WHERE code IS NOT NULL AND btrim(code) <> ''
    ) AS treatments_codes_group,

    (
      SELECT string_agg(DISTINCT t, '; ' ORDER BY t)
      FROM regexp_split_to_table(
             coalesce(r.additional_plasmids_injected,'') || ',' ||
             coalesce(r.additional_mrnas_injected,'')   || ',' ||
             coalesce(r.additonal_dye_and_chemicals,''),
             '[,;]'
           ) AS t
      WHERE btrim(t) <> ''
    ) AS treatments_names_group,

    (
      SELECT string_agg(DISTINCT t, '; ' ORDER BY t)
      FROM regexp_split_to_table(
             coalesce(r.zf_female_genotype,'')          || ',' ||
             coalesce(r.zf_male_genotype,'')            || ',' ||
             coalesce(r.additional_plasmids_injected,'')|| ',' ||
             coalesce(r.additional_mrnas_injected,'')   || ',' ||
             coalesce(r.additonal_dye_and_chemicals,''),
             '[,;]'
           ) AS t
      WHERE btrim(t) <> ''
    ) AS fluors_rollup

) AS roll ON TRUE;

COMMIT;

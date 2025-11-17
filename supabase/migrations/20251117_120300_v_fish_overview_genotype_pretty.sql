BEGIN;

DO $$
BEGIN
  IF to_regclass('public.v_fish_overview') IS NOT NULL THEN
    DROP VIEW public.v_fish_overview;
  END IF;
END
$$;

CREATE VIEW public.v_fish_overview AS
WITH
genotype_labels AS (
  SELECT
    jfg.fish_id,
    string_agg(
      DISTINCT COALESCE(g.genotype_name, g.genotype_code),
      '; ' ORDER BY COALESCE(g.genotype_name, g.genotype_code)
    ) AS genotype_label
  FROM public.join_fish_genotypes AS jfg
  JOIN public.genotypes AS g
    ON g.id = jfg.genotype_id
  GROUP BY jfg.fish_id
),

genotype_base_codes AS (
  SELECT
    jfta.fish_id,
    string_agg(
      DISTINCT jfta.transgene_base_code,
      ', ' ORDER BY jfta.transgene_base_code
    ) AS genotype_base_codes
  FROM public.join_fish_transgene_alleles AS jfta
  GROUP BY jfta.fish_id
),

plasmid_fish_fluors AS (
  SELECT DISTINCT
    jfta.fish_id,
    fl.fluor_code
  FROM public.join_fish_transgene_alleles AS jfta
  JOIN public.plasmids AS p
    ON p.plasmid_base_code = jfta.transgene_base_code
  JOIN public.join_plasmid_fusions AS jpf
    ON jpf.plasmid_id = p.id
  JOIN public.fusions AS fu
    ON fu.id = jpf.fusion_id
  JOIN public.fluors AS fl
    ON fl.id = fu.fluor_id
),

rna_fish_fluors AS (
  SELECT DISTINCT
    jfta.fish_id,
    fl.fluor_code
  FROM public.join_fish_transgene_alleles AS jfta
  JOIN public.rnas AS r
    ON r.rna_base_code = jfta.transgene_base_code
  JOIN public.join_rna_fusions AS jrf
    ON jrf.rna_id = r.id
  JOIN public.fusions AS fu
    ON fu.id = jrf.fusion_id
  JOIN public.fluors AS fl
    ON fl.id = fu.fluor_id
),

genotype_fluors AS (
  SELECT
    fish_id,
    string_agg(
      DISTINCT fluor_code,
      ', ' ORDER BY fluor_code
    ) AS genotype_fluors
  FROM (
    SELECT * FROM plasmid_fish_fluors
    UNION
    SELECT * FROM rna_fish_fluors
  ) AS src
  GROUP BY fish_id
),

treatment_base_codes_raw AS (
  SELECT
    ft.fish_id,
    d.dye_base_code AS base_code
  FROM public.join_fish_treatments AS ft
  JOIN public.join_treatment_dyes AS jtd
    ON jtd.treatment_id = ft.treatment_id
  JOIN public.dyes AS d
    ON d.id = jtd.dye_id

  UNION

  SELECT
    ft.fish_id,
    p.plasmid_base_code AS base_code
  FROM public.join_fish_treatments AS ft
  JOIN public.join_treatment_plasmids AS jtp
    ON jtp.treatment_id = ft.treatment_id
  JOIN public.plasmids AS p
    ON p.id = jtp.plasmid_id

  UNION

  SELECT
    ft.fish_id,
    r.rna_base_code AS base_code
  FROM public.join_fish_treatments AS ft
  JOIN public.join_treatment_rnas AS jtr
    ON jtr.treatment_id = ft.treatment_id
  JOIN public.rnas AS r
    ON r.id = jtr.rna_id
),

treatment_base_codes AS (
  SELECT
    fish_id,
    string_agg(
      DISTINCT base_code,
      ', ' ORDER BY base_code
    ) AS treatment_base_codes
  FROM treatment_base_codes_raw
  GROUP BY fish_id
),

treatment_plasmid_fluors AS (
  SELECT DISTINCT
    ft.fish_id,
    fl.fluor_code
  FROM public.join_fish_treatments AS ft
  JOIN public.join_treatment_plasmids AS jtp
    ON jtp.treatment_id = ft.treatment_id
  JOIN public.plasmids AS p
    ON p.id = jtp.plasmid_id
  JOIN public.join_plasmid_fusions AS jpf
    ON jpf.plasmid_id = p.id
  JOIN public.fusions AS fu
    ON fu.id = jpf.fusion_id
  JOIN public.fluors AS fl
    ON fl.id = fu.fluor_id
),

treatment_rna_fluors AS (
  SELECT DISTINCT
    ft.fish_id,
    fl.fluor_code
  FROM public.join_fish_treatments AS ft
  JOIN public.join_treatment_rnas AS jtr
    ON jtr.treatment_id = ft.treatment_id
  JOIN public.rnas AS r
    ON r.id = jtr.rna_id
  JOIN public.join_rna_fusions AS jrf
    ON jrf.rna_id = r.id
  JOIN public.fusions AS fu
    ON fu.id = jrf.fusion_id
  JOIN public.fluors AS fl
    ON fl.id = fu.fluor_id
),

treatment_fluors AS (
  SELECT
    fish_id,
    string_agg(
      DISTINCT fluor_code,
      ', ' ORDER BY fluor_code
    ) AS treatment_fluors
  FROM (
    SELECT * FROM treatment_plasmid_fluors
    UNION
    SELECT * FROM treatment_rna_fluors
  ) AS src
  GROUP BY fish_id
),

all_base_codes AS (
  SELECT
    fish_id,
    string_agg(
      DISTINCT base_code,
      ', ' ORDER BY base_code
    ) AS all_base_codes
  FROM (
    SELECT
      jfta.fish_id,
      jfta.transgene_base_code AS base_code
    FROM public.join_fish_transgene_alleles AS jfta

    UNION

    SELECT
      tbc.fish_id,
      tbc.base_code
    FROM treatment_base_codes_raw AS tbc
  ) AS src
  GROUP BY fish_id
),

all_fluor_codes AS (
  SELECT
    fish_id,
    fluor_code
  FROM (
    SELECT * FROM plasmid_fish_fluors
    UNION
    SELECT * FROM rna_fish_fluors
    UNION
    SELECT * FROM treatment_plasmid_fluors
    UNION
    SELECT * FROM treatment_rna_fluors
  ) AS src
),

all_fluors AS (
  SELECT
    fish_id,
    string_agg(
      DISTINCT fluor_code,
      ', ' ORDER BY fluor_code
    ) AS all_fluors
  FROM all_fluor_codes
  GROUP BY fish_id
)

SELECT
  f.id                 AS fish_id,
  f.fish_code          AS fish_code,
  f.birthday           AS birthday,
  f.genetic_background AS genetic_background,
  f.line_building_stage,
  f.nickname,
  f.notes,
  f.created_at,

  COALESCE(gl.genotype_label, gbc.genotype_base_codes) AS genotype_pretty,
  gbc.genotype_base_codes,
  gf.genotype_fluors,

  tbc.treatment_base_codes,
  tf.treatment_fluors,

  abc.all_base_codes,
  af.all_fluors

FROM public.fish_instance AS f
LEFT JOIN genotype_labels      AS gl  ON gl.fish_id  = f.id
LEFT JOIN genotype_base_codes  AS gbc ON gbc.fish_id = f.id
LEFT JOIN genotype_fluors      AS gf  ON gf.fish_id  = f.id
LEFT JOIN treatment_base_codes AS tbc ON tbc.fish_id = f.id
LEFT JOIN treatment_fluors     AS tf  ON tf.fish_id  = f.id
LEFT JOIN all_base_codes       AS abc ON abc.fish_id = f.id
LEFT JOIN all_fluors           AS af  ON af.fish_id  = f.id;

COMMIT;

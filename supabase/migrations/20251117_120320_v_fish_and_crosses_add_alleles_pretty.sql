BEGIN;

-- Drop dependent views in the right order
DROP VIEW IF EXISTS public.v_crosses_overview;
DROP VIEW IF EXISTS public.v_fish_overview;

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

-- Allele-level pretty labels: Tg(basecode)allele_nickname/allele_name/allele_number
allele_labels AS (
  SELECT
    jfta.fish_id,
    string_agg(
      DISTINCT
        'Tg(' || ta.transgene_base_code || ')' ||
        COALESCE(
          NULLIF(ta.allele_nickname, ''),
          NULLIF(ta.allele_name, ''),
          ta.allele_number::text,
          ''
        ),
      '; ' ORDER BY ta.transgene_base_code,
                     COALESCE(
                       NULLIF(ta.allele_nickname, ''),
                       NULLIF(ta.allele_name, ''),
                       ta.allele_number::text,
                       ''
                     )
    ) AS genotype_alleles_pretty
  FROM public.join_fish_transgene_alleles AS jfta
  JOIN public.transgene_alleles AS ta
    ON ta.transgene_base_code = jfta.transgene_base_code
   AND ta.allele_number       = jfta.allele_number
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

  COALESCE(gl.genotype_label, al.genotype_alleles_pretty, gbc.genotype_base_codes)
    AS genotype_pretty,
  al.genotype_alleles_pretty,
  gbc.genotype_base_codes,
  gf.genotype_fluors,

  tbc.treatment_base_codes,
  tf.treatment_fluors,

  abc.all_base_codes,
  af.all_fluors

FROM public.fish_instance AS f
LEFT JOIN genotype_labels      AS gl  ON gl.fish_id  = f.id
LEFT JOIN allele_labels        AS al  ON al.fish_id  = f.id
LEFT JOIN genotype_base_codes  AS gbc ON gbc.fish_id = f.id
LEFT JOIN genotype_fluors      AS gf  ON gf.fish_id  = f.id
LEFT JOIN treatment_base_codes AS tbc ON tbc.fish_id = f.id
LEFT JOIN treatment_fluors     AS tf  ON tf.fish_id  = f.id
LEFT JOIN all_base_codes       AS abc ON abc.fish_id = f.id
LEFT JOIN all_fluors           AS af  ON af.fish_id  = f.id;

-- Recreate v_crosses_overview to include allele-pretty labels too
CREATE VIEW public.v_crosses_overview AS
WITH fish AS (
  SELECT
    f.fish_id,
    f.fish_code,
    f.genotype_pretty,
    f.genotype_alleles_pretty,
    f.genotype_base_codes,
    f.genotype_fluors,
    f.treatment_base_codes,
    f.treatment_fluors,
    f.all_base_codes,
    f.all_fluors
  FROM public.v_fish_overview AS f
),
cross_clutch AS (
  SELECT
    c.id             AS cross_id,
    c.cross_run_code,
    c.female_fish_id,
    c.male_fish_id,
    COUNT(DISTINCT cl.id) AS n_clutches,
    MIN(cl.clutch_date)   AS first_clutch_date,
    MAX(cl.clutch_date)   AS last_clutch_date
  FROM public.crosses AS c
  LEFT JOIN public.clutches AS cl
    ON cl.cross_id = c.id
  GROUP BY
    c.id,
    c.cross_run_code,
    c.female_fish_id,
    c.male_fish_id
)
SELECT
  cc.cross_id,
  cc.cross_run_code,
  cc.female_fish_id,
  cc.male_fish_id,

  fm.fish_code AS female_parent_code,
  fd.fish_code AS male_parent_code,

  (fm.fish_code || ' × ' || fd.fish_code) AS cross_label,

  fm.genotype_pretty AS female_genotype_pretty,
  fd.genotype_pretty AS male_genotype_pretty,
  (fm.genotype_pretty || ' × ' || fd.genotype_pretty)
    AS genotype_cross_label,

  fm.genotype_alleles_pretty AS female_genotype_alleles_pretty,
  fd.genotype_alleles_pretty AS male_genotype_alleles_pretty,
  (fm.genotype_alleles_pretty || ' × ' || fd.genotype_alleles_pretty)
    AS allele_cross_label,

  fm.genotype_base_codes AS female_genotype_base_codes,
  fd.genotype_base_codes AS male_genotype_base_codes,
  (fm.genotype_base_codes || ' × ' || fd.genotype_base_codes)
    AS base_code_cross_label,

  fm.genotype_fluors AS female_genotype_fluors,
  fd.genotype_fluors AS male_genotype_fluors,
  (fm.genotype_fluors || ' × ' || fd.genotype_fluors)
    AS fusion_cross_label,

  fm.treatment_base_codes AS female_treatment_base_codes,
  fd.treatment_base_codes AS male_treatment_base_codes,
  (fm.treatment_base_codes || ' × ' || fd.treatment_base_codes)
    AS treatment_cross_label,

  fm.treatment_fluors AS female_treatment_fluors,
  fd.treatment_fluors AS male_treatment_fluors,
  (fm.treatment_fluors || ' × ' || fd.treatment_fluors)
    AS treatment_fluor_cross_label,

  fm.all_base_codes AS female_all_base_codes,
  fd.all_base_codes AS male_all_base_codes,
  (fm.all_base_codes || ' × ' || fd.all_base_codes)
    AS all_base_codes_cross_label,

  fm.all_fluors AS female_all_fluors,
  fd.all_fluors AS male_all_fluors,
  (fm.all_fluors || ' × ' || fd.all_fluors)
    AS all_fluors_cross_label,

  cc.n_clutches,
  cc.first_clutch_date,
  cc.last_clutch_date

FROM cross_clutch AS cc
JOIN fish AS fm
  ON fm.fish_id = cc.female_fish_id
JOIN fish AS fd
  ON fd.fish_id = cc.male_fish_id;

COMMIT;

BEGIN;

DO $$
BEGIN
  IF to_regclass('public.v_crosses_overview') IS NOT NULL THEN
    DROP VIEW public.v_crosses_overview;
  END IF;
END
$$;

CREATE VIEW public.v_crosses_overview AS
WITH fish AS (
  SELECT
    f.fish_id,
    f.fish_code,
    f.genotype_pretty,
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

  -- basic cross label (mom × dad)
  (fm.fish_code || ' × ' || fd.fish_code) AS cross_label,

  -- genotype pretty
  fm.genotype_pretty AS female_genotype_pretty,
  fd.genotype_pretty AS male_genotype_pretty,
  (fm.genotype_pretty || ' × ' || fd.genotype_pretty)
    AS genotype_cross_label,

  -- genotype base-code cross
  fm.genotype_base_codes AS female_genotype_base_codes,
  fd.genotype_base_codes AS male_genotype_base_codes,
  (fm.genotype_base_codes || ' × ' || fd.genotype_base_codes)
    AS base_code_cross_label,

  -- fusion / fluor cross (genotype-based)
  fm.genotype_fluors AS female_genotype_fluors,
  fd.genotype_fluors AS male_genotype_fluors,
  (fm.genotype_fluors || ' × ' || fd.genotype_fluors)
    AS fusion_cross_label,

  -- treatment base-code cross
  fm.treatment_base_codes AS female_treatment_base_codes,
  fd.treatment_base_codes AS male_treatment_base_codes,
  (fm.treatment_base_codes || ' × ' || fd.treatment_base_codes)
    AS treatment_cross_label,

  -- treatment fluor cross
  fm.treatment_fluors AS female_treatment_fluors,
  fd.treatment_fluors AS male_treatment_fluors,
  (fm.treatment_fluors || ' × ' || fd.treatment_fluors)
    AS treatment_fluor_cross_label,

  -- all base codes (treatment > genotype)
  fm.all_base_codes AS female_all_base_codes,
  fd.all_base_codes AS male_all_base_codes,
  (fm.all_base_codes || ' × ' || fd.all_base_codes)
    AS all_base_codes_cross_label,

  -- all fluors (treatment > genotype)
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

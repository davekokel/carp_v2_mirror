BEGIN;

-- Drop dependent views first
DROP VIEW IF EXISTS public.v11_cross_star;
DROP VIEW IF EXISTS public.v11_tank_star;
DROP VIEW IF EXISTS public.v11_line_allele_rollups;

-- 1) Per-line allele rollups: canonical + label
CREATE VIEW public.v11_line_allele_rollups AS
WITH per_allele AS (
  SELECT
    fl.id AS line_id,

    -- canonical: Tg(basecode)allele_name
    'Tg(' || ta.transgene_base_code || ')' ||
      COALESCE(ta.allele_name, '') AS canonical,

    -- label: Tg(basecode)nickname_or_name (nickname if present, else allele_name)
    'Tg(' || ta.transgene_base_code || ')' ||
      COALESCE(NULLIF(ta.allele_nickname, ''), ta.allele_name, '') AS label
  FROM public.fish_lines fl
  JOIN public.join_line_alleles jla
    ON jla.line_id = fl.id
  JOIN public.constructs c
    ON c.id = jla.construct_id
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = c.base_code
   AND ta.allele_number       = jla.allele_number
)
SELECT
  line_id,
  string_agg(DISTINCT canonical, '; ' ORDER BY canonical) AS allele_canonical_rollup,
  string_agg(DISTINCT label,     '; ' ORDER BY label)     AS allele_label_rollup
FROM per_allele
GROUP BY line_id;

-- 2) Cross star: mom/dad allele_canonical + allele_label + organelle-fluor
CREATE VIEW public.v11_cross_star AS
WITH fis AS (
  SELECT
    fish_instance_id,
    fish_code,
    line_id,
    genotype_pretty,
    all_organelle_fluor_rollup
  FROM public.v11_fish_instance_star
)
SELECT
  cr.id::uuid::text         AS cross_id,
  COALESCE(cr.cross_run_code, tp.tank_pair_code || ' @ ' || cr.created_at::date::text)
                             AS cross_code,
  cr.created_at::date       AS cross_date,
  tp.tank_pair_code         AS tank_pair_code,

  tm.tank_code              AS mom_tank_code,
  tf.tank_code              AS dad_tank_code,

  COALESCE(fm.genotype_pretty,'') AS mom_genotype_pretty,
  COALESCE(ff.genotype_pretty,'') AS dad_genotype_pretty,

  COALESCE(lm.allele_canonical_rollup,'') AS mom_allele_canonical,
  COALESCE(lf.allele_canonical_rollup,'') AS dad_allele_canonical,

  COALESCE(lm.allele_label_rollup,'')     AS mom_allele_label,
  COALESCE(lf.allele_label_rollup,'')     AS dad_allele_label,

  COALESCE(fm.all_organelle_fluor_rollup,'') AS mom_organelle_fluor_rollup,
  COALESCE(ff.all_organelle_fluor_rollup,'') AS dad_organelle_fluor_rollup

FROM public.crosses cr
LEFT JOIN public.tank_pairs tp ON tp.id = cr.tank_pair_id

LEFT JOIN public.tanks tm ON tm.id = tp.mother_tank_id
LEFT JOIN public.tanks tf ON tf.id = tp.father_tank_id

LEFT JOIN public.fish_instances_v10 fim ON fim.id = tm.fish_instance_id
LEFT JOIN public.fish_instances_v10 fif ON fif.id = tf.fish_instance_id

LEFT JOIN fis fm ON fm.fish_instance_id = fim.id
LEFT JOIN fis ff ON ff.fish_instance_id = fif.id

LEFT JOIN public.v11_line_allele_rollups lm ON lm.line_id = fim.line_id
LEFT JOIN public.v11_line_allele_rollups lf ON lf.line_id = fif.line_id;

-- 3) Tank star: tank_code, allele_canonical + allele_label + organelle-fluor + stage + dob
CREATE VIEW public.v11_tank_star AS
WITH fis AS (
  SELECT
    fish_instance_id,
    fish_code,
    line_id,
    birthday,
    line_building_stage,
    all_organelle_fluor_rollup
  FROM public.v11_fish_instance_star
)
SELECT
  t.id::text                              AS tank_id,
  t.tank_code                             AS tank_code_raw,
  CASE
    WHEN t.tank_code LIKE 'TANK-FSH-%'
      THEN 'TANK-' || substring(t.tank_code FROM '^TANK-FSH-(.*)$')
    ELSE t.tank_code
  END                                     AS tank_code,
  COALESCE(fi.fish_code, fis.fish_code)   AS fish_code,
  COALESCE(la.allele_canonical_rollup,'') AS allele_canonical,
  COALESCE(la.allele_label_rollup,'')     AS allele_label,
  COALESCE(fis.all_organelle_fluor_rollup,'') AS organelle_fluor,
  COALESCE(fis.line_building_stage,'')    AS line_building_stage,
  fis.birthday                            AS dob
FROM public.tanks t
LEFT JOIN public.fish_instances_v10 fi ON fi.id = t.fish_instance_id
LEFT JOIN fis ON fis.fish_instance_id = t.fish_instance_id
LEFT JOIN public.v11_line_allele_rollups la ON la.line_id = fis.line_id;

COMMIT;

BEGIN;

-- 1) Per-line allele rollups
DROP VIEW IF EXISTS public.v11_line_allele_rollups;

CREATE VIEW public.v11_line_allele_rollups AS
WITH per_allele AS (
  SELECT
    fl.id AS line_id,

    -- canonical: Tg(basecode)allele_name
    'Tg(' || ta.transgene_base_code || ')' ||
      COALESCE(ta.allele_name, '') AS canonical,

    -- nickname_or_name: Tg(basecode)nickname_if_present_else_name
    'Tg(' || ta.transgene_base_code || ')' ||
      COALESCE(NULLIF(ta.allele_nickname, ''), ta.allele_name, '') AS nickname
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
  string_agg(DISTINCT nickname,  '; ' ORDER BY nickname)  AS allele_nickname_rollup
FROM per_allele
GROUP BY line_id;

-- 2) Cross star view with mom/dad standard fields + allele rollups
DROP VIEW IF EXISTS public.v11_cross_star;

CREATE VIEW public.v11_cross_star AS
WITH fis AS (
  SELECT
    fish_instance_id,
    fish_code,
    genotype_pretty,
    genotype_basecode_code,
    genotype_transgene_allele_code,
    all_fluor_tag_rollup,
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

  COALESCE(am.allele_canonical_rollup,'')  AS mom_allele_canonical,
  COALESCE(af.allele_canonical_rollup,'')  AS dad_allele_canonical,

  COALESCE(am.allele_nickname_rollup,'')   AS mom_allele_nicknames,
  COALESCE(af.allele_nickname_rollup,'')   AS dad_allele_nicknames,

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

LEFT JOIN public.v11_line_allele_rollups am ON am.line_id = fim.line_id
LEFT JOIN public.v11_line_allele_rollups af ON af.line_id = fif.line_id;

COMMIT;

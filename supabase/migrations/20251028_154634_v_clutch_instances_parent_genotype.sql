BEGIN;
/*
  Derive clutch_genotype_pretty from parents:
  clutch_genotype_pretty := trim(mom.genotype_rollup || ' × ' || dad.genotype_rollup)
*/
CREATE OR REPLACE VIEW public.v_clutch_instances AS
WITH t AS (
  SELECT cit.clutch_instance_id AS ci_id,
         count(*)::int AS treatments_count_effective,
         COALESCE(string_agg(DISTINCT cit.material_code, ' + '), '') AS treatments_pretty_effective
  FROM public.clutch_instance_treatments cit
  GROUP BY cit.clutch_instance_id
),
parents AS (
  SELECT
    fp.fish_pair_code,
    fm.fish_uuid AS mom_uuid,
    fd.fish_uuid AS dad_uuid
  FROM public.fish_pairs fp
  JOIN public.fish fm ON fm.fish_uuid = fp.mom_fish_id
  JOIN public.fish fd ON fd.fish_uuid = fp.dad_fish_id
),
pg AS (
  SELECT
    p.fish_pair_code,
    COALESCE(mr.genotype_rollup, '') AS mom_rollup,
    COALESCE(dr.genotype_rollup, '') AS dad_rollup
  FROM parents p
  LEFT JOIN public.v_fish_rich mr ON mr.fish_uuid = p.mom_uuid
  LEFT JOIN public.v_fish_rich dr ON dr.fish_uuid = p.dad_uuid
),
base AS (
  SELECT
    COALESCE(ci.clutch_instance_code, 'CI-' || substr(ci.id::text, 1, 8)) AS clutch_code,
    (COALESCE(x.cross_date, x.created_at::date, ci.created_at::date) + INTERVAL '1 day')::date AS clutch_birthday,
    COALESCE(x.cross_run_code, '') AS cross_name_pretty,
    ''::text AS clutch_name,
    /* derive 'genotype' from parents */
    trim(BOTH ' ' FROM
      CASE
        WHEN COALESCE(pg.mom_rollup,'') <> '' AND COALESCE(pg.dad_rollup,'') <> '' THEN pg.mom_rollup || ' × ' || pg.dad_rollup
        WHEN COALESCE(pg.mom_rollup,'') <> '' THEN pg.mom_rollup
        WHEN COALESCE(pg.dad_rollup,'') <> '' THEN pg.dad_rollup
        ELSE ''
      END
    ) AS clutch_genotype_pretty,
    ''::text AS clutch_strain_pretty,
    COALESCE(t.treatments_count_effective, 0) AS treatments_count_effective,
    COALESCE(t.treatments_pretty_effective, '') AS treatments_pretty_effective,
    /* keep legacy rollup for compatibility; display view formats it */
    NULLIF(trim(
      COALESCE(t.treatments_pretty_effective,'')
    ), '') AS genotype_treatment_rollup_effective,
    COALESCE(x.created_by, '') AS created_by_instance,
    ci.created_at AS created_at_instance
  FROM public.clutch_instances ci
  LEFT JOIN public.cross_instances x ON x.id = ci.cross_instance_id
  LEFT JOIN t  ON t.ci_id = ci.id
  LEFT JOIN pg ON pg.fish_pair_code = x.fish_pair_code
)
SELECT
  clutch_code,
  clutch_birthday,
  cross_name_pretty,
  clutch_name,
  clutch_genotype_pretty,
  clutch_strain_pretty,
  treatments_count_effective,
  treatments_pretty_effective,
  genotype_treatment_rollup_effective,
  created_by_instance,
  created_at_instance
FROM base
ORDER BY created_at_instance DESC NULLS LAST, clutch_code;
COMMIT;

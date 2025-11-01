BEGIN;

-- 1) Canonical link table: clutch ↔ treatment
CREATE TABLE IF NOT EXISTS public.join_clutch_treatments (
  clutch_instance_id uuid NOT NULL REFERENCES public.clutch_instances(id) ON DELETE CASCADE,
  treatment_type     text,
  treatment_code     text,
  treatment_name     text,
  notes              text,
  created_by         text,
  created_at         timestamptz NOT NULL DEFAULT now()
);

-- De-dupe per clutch on normalized (type, code)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='join_clutch_treatments' AND indexname='uq_jct_unique'
  ) THEN
    EXECUTE $ix$
      CREATE UNIQUE INDEX uq_jct_unique
      ON public.join_clutch_treatments (
        clutch_instance_id,
        lower(coalesce(treatment_type,'')),
        lower(coalesce(treatment_code,''))
      )
    $ix$;
  END IF;
END $$;

-- Helper indexes
CREATE INDEX IF NOT EXISTS ix_jct_clutch ON public.join_clutch_treatments(clutch_instance_id);
CREATE INDEX IF NOT EXISTS ix_jct_type   ON public.join_clutch_treatments(lower(treatment_type));
CREATE INDEX IF NOT EXISTS ix_jct_code   ON public.join_clutch_treatments(lower(treatment_code));

-- 2) Recreate view with the strict contract your page expects
DROP VIEW IF EXISTS public.v_clutch_instances;

CREATE VIEW public.v_clutch_instances AS
WITH j AS (
  -- Prefer registry name; fallback to stored name or code
  SELECT
    jct.clutch_instance_id,
    COALESCE(vm.material_name, jct.treatment_name, jct.treatment_code) AS pretty_name
  FROM public.join_clutch_treatments jct
  LEFT JOIN public.v_materials vm
    ON lower(vm.material_type)=lower(jct.treatment_type)
   AND lower(vm.material_code)=lower(jct.treatment_code)
),
roll AS (
  SELECT
    clutch_instance_id,
    COUNT(*)::int AS treatments_count_effective,
    string_agg(
      DISTINCT NULLIF(btrim(pretty_name), ''),
      ' + ' ORDER BY NULLIF(btrim(pretty_name), '')
    ) AS treatments_pretty_effective
  FROM j
  GROUP BY clutch_instance_id
),
base AS (
  SELECT
    ci.clutch_instance_code                 AS clutch_code,
    (cr.cross_date + INTERVAL '1 day')::date AS clutch_birthday,
    COALESCE(
      'CR(' || cr.cross_run_code || ') • ' ||
      COALESCE(vtp.mom_fish_code,'?') || ' × ' || COALESCE(vtp.dad_fish_code,'?'),
      'CR • ' || COALESCE(cr.tank_pair_code,'?')
    ) AS cross_name_pretty,
    ''::text                                AS clutch_name,
    COALESCE(ci.clutch_genotype_pretty,'')  AS clutch_genotype_pretty,
    ''::text                                AS clutch_strain_pretty,
    COALESCE(roll.treatments_count_effective,0)::int AS treatments_count_effective,
    COALESCE(roll.treatments_pretty_effective,'')     AS treatments_pretty_effective,
    CASE
      WHEN COALESCE(roll.treatments_pretty_effective,'') <> '' AND COALESCE(ci.clutch_genotype_pretty,'') <> ''
        THEN roll.treatments_pretty_effective || ' > ' || ci.clutch_genotype_pretty
      WHEN COALESCE(roll.treatments_pretty_effective,'') <> ''
        THEN roll.treatments_pretty_effective
      ELSE COALESCE(ci.clutch_genotype_pretty,'')
    END AS genotype_treatment_rollup_effective,
    COALESCE(ci.created_by, cr.created_by, '')    AS created_by_instance,
    COALESCE(ci.created_at, cr.created_at, now()) AS created_at_instance
  FROM public.clutch_instances ci
  LEFT JOIN public.crosses      cr  ON cr.id = ci.cross_instance_id
  LEFT JOIN public.v_tank_pairs vtp ON vtp.tank_pair_code = cr.tank_pair_code
  LEFT JOIN roll                ON roll.clutch_instance_id = ci.id
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

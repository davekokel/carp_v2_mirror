BEGIN;

-- Drop dependents safely
DROP VIEW IF EXISTS public.v_overview_mounts;
DROP VIEW IF EXISTS public.v_clutches_for_entry;
DROP VIEW IF EXISTS public.v_clutch_instances_display;

-- Core display view (depends only on v_clutch_instances)
CREATE VIEW public.v_clutch_instances_display
( 
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
  created_at_instance,
  clutch_label,
  genotype_label,
  parent_genotype_pretty
) AS
SELECT
  vci.clutch_code,
  vci.clutch_birthday,
  COALESCE(vci.cross_name_pretty,'')                              AS cross_name_pretty,
  COALESCE(vci.clutch_name,'')                                    AS clutch_name,
  COALESCE(vci.clutch_genotype_pretty,'')                         AS clutch_genotype_pretty,
  COALESCE(vci.clutch_strain_pretty,'')                           AS clutch_strain_pretty,
  COALESCE(vci.treatments_count_effective,0)::int                 AS treatments_count_effective,
  COALESCE(vci.treatments_pretty_effective,'')                    AS treatments_pretty_effective,
  COALESCE(
    vci.genotype_treatment_rollup_effective,
    CASE
      WHEN COALESCE(vci.treatments_pretty_effective,'') <> '' AND COALESCE(vci.clutch_genotype_pretty,'') <> ''
        THEN vci.treatments_pretty_effective || ' > ' || vci.clutch_genotype_pretty
      WHEN COALESCE(vci.treatments_pretty_effective,'') <> ''
        THEN vci.treatments_pretty_effective
      ELSE COALESCE(vci.clutch_genotype_pretty,'')
    END
  )                                                               AS genotype_treatment_rollup_effective,
  COALESCE(vci.created_by_instance,'')                             AS created_by_instance,
  vci.created_at_instance                                          AS created_at_instance,
  COALESCE(NULLIF(vci.clutch_name,''), vci.clutch_code)            AS clutch_label,
  COALESCE(NULLIF(vci.clutch_genotype_pretty,''), vci.treatments_pretty_effective, '') AS genotype_label,
  ''::text                                                         AS parent_genotype_pretty
FROM public.v_clutch_instances vci
ORDER BY vci.clutch_code;

-- v_clutches_for_entry simply mirrors v_clutch_instances
CREATE VIEW public.v_clutches_for_entry AS
SELECT *
FROM public.v_clutch_instances
ORDER BY clutch_code;

-- v_overview_mounts: only create if base table exists
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='mounts'
  ) THEN
    EXECUTE $v$
      CREATE OR REPLACE VIEW public.v_overview_mounts AS
      SELECT
        m.mount_code,
        m.time_mounted,
        m.mounting_orientation,
        m.clutch_instance_id,
        NULL::int  AS treatments_count_effective,
        NULL::text AS treatments_pretty_effective,
        NULL::text AS genotype_treatment_rollup_effective,
        NULL::text AS parent_genotype_pretty
      FROM public.mounts m
      ORDER BY m.time_mounted DESC NULLS LAST;
    $v$;
  ELSE
    RAISE NOTICE 'Skipping v_overview_mounts creation: table public.mounts not yet defined.';
  END IF;
END $$;

COMMIT;
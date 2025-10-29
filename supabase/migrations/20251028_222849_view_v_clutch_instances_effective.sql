BEGIN;

-- Canonical "effective" view: stored (ci) → view (v) → local fallback
CREATE OR REPLACE VIEW public.v_clutch_instances_effective AS
SELECT
  v.clutch_code,
  v.clutch_birthday,
  v.cross_name_pretty,

  /* Effective name/genotype */
  COALESCE(NULLIF(v.clutch_name,''), v.clutch_code)                      AS clutch_name_effective,
  COALESCE(NULLIF(ci.clutch_genotype_pretty,''), NULLIF(v.clutch_genotype_pretty,''), '') AS clutch_genotype_effective,

  /* Counts and pretty list from the display view */
  COALESCE(v.treatments_count_effective, 0)::int                         AS treatments_count_effective,
  COALESCE(v.treatments_pretty_effective, '')                            AS treatments_pretty_effective,

  /* Effective rollup: stored → view → local(treatments > genotype) */
  COALESCE(
    NULLIF(ci.treatments_genotype_rollup,''),
    NULLIF(v.genotype_treatment_rollup_effective,''),
    CASE
      WHEN COALESCE(v.treatments_pretty_effective,'') <> '' AND COALESCE(v.clutch_genotype_pretty,'') <> ''
        THEN v.treatments_pretty_effective || ' > ' || v.clutch_genotype_pretty
      WHEN COALESCE(v.treatments_pretty_effective,'') <> ''
        THEN v.treatments_pretty_effective
      ELSE COALESCE(v.clutch_genotype_pretty,'')
    END
  )                                                                       AS treatments_genotype_effective,

  /* Provenance / audit */
  v.created_by_instance,
  v.created_at_instance

FROM public.v_clutch_instances_display v
JOIN public.clutch_instances ci
  ON ci.clutch_instance_code = v.clutch_code
ORDER BY v.created_at_instance DESC NULLS LAST, v.clutch_code;

COMMIT;

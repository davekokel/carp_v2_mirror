BEGIN;

-- Always drop first so we can change shape safely
DROP VIEW IF EXISTS public.v_clutch_instances;

-- Minimal, deterministic contract view for “Add treatments to clutch”
-- Source of truth: public.clutch_instances (ci) + public.crosses (cr)
CREATE VIEW public.v_clutch_instances AS
SELECT
  -- required by the picker
  ci.clutch_instance_code                                  AS clutch_code,
  cr.cross_date::date                                       AS clutch_birthday,
  cr.cross_run_code                                         AS cross_name_pretty,
  ci.clutch_instance_code                                   AS clutch_name,                 -- placeholder (no separate name column today)
  COALESCE(ci.clutch_genotype_pretty,'')                    AS clutch_genotype_pretty,
  ''::text                                                  AS clutch_strain_pretty,        -- not modeled; keep empty

  -- legacy/effective rollups (the page shows them; keep empty until you roll a materialized lineage)
  0::int                                                    AS treatments_count_effective,
  ''::text                                                  AS treatments_pretty_effective,
  ''::text                                                  AS genotype_treatment_rollup_effective,

  -- instance provenance (what the page labels “plan/instance”)
  COALESCE(cr.created_by,'')                                AS created_by_instance,
  COALESCE(ci.created_at, cr.created_at)                    AS created_at_instance,

  -- extra fields the page reads in the summary section (keep empty if you don't compute lineage yet)
  ''::text                                                  AS clutch_treatments_codes,
  ''::text                                                  AS clutch_treatments_names,
  ''::text                                                  AS clutch_treatments_fusions,
  ''::text                                                  AS clutch_genotype_fusions,
  ''::text                                                  AS clutch_lineage_pretty,
  ''::text                                                  AS clutch_lineage_fusions_pretty,
  ''::text                                                  AS clutch_lineage_full_fusions_pretty

FROM public.clutch_instances  ci
JOIN public.crosses           cr  ON cr.id = ci.cross_instance_id;

COMMIT;

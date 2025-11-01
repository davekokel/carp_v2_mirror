-- ============================================================================
-- public.v_clutch_treatments
-- Compatible logical rollup for clutch → treatment summary
-- Source of truth: clutch_materials + v_materials
-- Emits canonical *_effective column names expected by v_clutch_instances_effective
-- ============================================================================
CREATE OR REPLACE VIEW public.v_clutch_treatments AS
WITH base AS (
  SELECT
    cm.clutch_instance_id,
    cm.created_at,
    COALESCE(cm.material_name, vm.material_name) AS material_name
  FROM public.clutch_materials cm
  LEFT JOIN public.v_materials vm
    ON lower(vm.material_type) = lower(cm.material_type)
   AND lower(vm.material_code) = lower(cm.material_code)
)
, agg AS (
  SELECT
    b.clutch_instance_id,
    COUNT(*)::int AS treatments_count_effective,
    string_agg(DISTINCT b.material_name, ' + ' ORDER BY b.material_name)
      AS treatments_pretty_effective,
    MAX(b.created_at) AS last_treatment_at
  FROM base b
  GROUP BY b.clutch_instance_id
)
SELECT * FROM agg;

COMMENT ON VIEW public.v_clutch_treatments IS
  'Canonical clutch-level treatments rollup view (from clutch_materials + v_materials). Emits *_effective columns used by v_clutch_instances_effective.';

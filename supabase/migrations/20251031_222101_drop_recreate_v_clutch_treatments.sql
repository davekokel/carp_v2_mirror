-- Force drop and clean recreate v_clutch_treatments with canonical column names
DO $$
BEGIN
  IF to_regclass('public.v_clutch_treatments') IS NOT NULL THEN
    EXECUTE 'DROP VIEW public.v_clutch_treatments CASCADE';
  END IF;
END$$;

CREATE VIEW public.v_clutch_treatments AS
WITH base AS (
  SELECT
    cm.clutch_instance_id,
    cm.created_at,
    COALESCE(cm.material_name, vm.material_name) AS material_name
  FROM public.clutch_materials cm
  LEFT JOIN public.v_materials vm
    ON lower(vm.material_type)=lower(cm.material_type)
   AND lower(vm.material_code)=lower(cm.material_code)
),
agg AS (
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
  'Canonical clutch-level treatment rollup (count/pretty/last) from clutch_materials + v_materials.';

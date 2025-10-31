-- Normalize v_clutch_treatments during rebuild:
-- 1) Replace the view body using legacy output names (safe for CREATE OR REPLACE)
-- 2) Rename legacy output columns to canonical *_effective if present

-- Step 1: CREATE OR REPLACE with legacy names
CREATE OR REPLACE VIEW public.v_clutch_treatments AS
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
    COUNT(*)::int AS treatments_count,  -- legacy
    string_agg(DISTINCT b.material_name, ' + ' ORDER BY b.material_name)
      AS treatments_pretty,             -- legacy
    MAX(b.created_at) AS last_treatment_at
  FROM base b
  GROUP BY b.clutch_instance_id
)
SELECT * FROM agg;

-- Step 2: rename legacy columns to canonical names if needed
DO $$
DECLARE
  has_count_legacy  boolean;
  has_pretty_legacy boolean;
  has_count_eff     boolean;
  has_pretty_eff    boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='v_clutch_treatments'
      AND column_name='treatments_count'
  ) INTO has_count_legacy;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='v_clutch_treatments'
      AND column_name='treatments_pretty'
  ) INTO has_pretty_legacy;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='v_clutch_treatments'
      AND column_name='treatments_count_effective'
  ) INTO has_count_eff;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='v_clutch_treatments'
      AND column_name='treatments_pretty_effective'
  ) INTO has_pretty_eff;

  IF has_count_legacy AND NOT has_count_eff THEN
    EXECUTE 'ALTER VIEW public.v_clutch_treatments RENAME COLUMN treatments_count TO treatments_count_effective';
  END IF;

  IF has_pretty_legacy AND NOT has_pretty_eff THEN
    EXECUTE 'ALTER VIEW public.v_clutch_treatments RENAME COLUMN treatments_pretty TO treatments_pretty_effective';
  END IF;
END
$$;

COMMENT ON VIEW public.v_clutch_treatments IS
  'Clutch-level treatments rollup (count/pretty/last) from clutch_materials + v_materials; emits canonical *_effective columns.';

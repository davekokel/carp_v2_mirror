-- Normalize v_clutch_treatments to emit canonical *_effective columns
-- and compute from clutch_materials + v_materials.

-- 0) helpful index (no-op if exists)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='ix_clutch_materials_instance') THEN
    EXECUTE 'CREATE INDEX ix_clutch_materials_instance ON public.clutch_materials (clutch_instance_id)';
  END IF;
END
$$;

-- 1) Replace the view body but do NOT attempt to change column names here.
--    We will rename columns in step 2 if needed.
--    We emit LEGACY names in this step to satisfy CREATE OR REPLACE.
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
    COUNT(*)::int AS treatments_count,                                     -- legacy out name
    string_agg(DISTINCT b.material_name, ' + ' ORDER BY b.material_name)
      AS treatments_pretty,                                                -- legacy out name
    MAX(b.created_at) AS last_treatment_at
  FROM base b
  GROUP BY b.clutch_instance_id
)
SELECT * FROM agg;

COMMENT ON VIEW public.v_clutch_treatments IS
  'Clutch-level treatments rollup from clutch_materials + v_materials. Emits count/pretty/last timestamp.';

-- 2) If the view still has legacy column names, rename them to canonical *_effective.
DO $$
DECLARE
  has_count_eff  boolean;
  has_pretty_eff boolean;
  has_count_legacy  boolean;
  has_pretty_legacy boolean;
BEGIN
  SELECT EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema='public' AND table_name='v_clutch_treatments'
             AND column_name='treatments_count_effective'
         )
    INTO has_count_eff;

  SELECT EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema='public' AND table_name='v_clutch_treatments'
             AND column_name='treatments_pretty_effective'
         )
    INTO has_pretty_eff;

  SELECT EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema='public' AND table_name='v_clutch_treatments'
             AND column_name='treatments_count'
         )
    INTO has_count_legacy;

  SELECT EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema='public' AND table_name='v_clutch_treatments'
             AND column_name='treatments_pretty'
         )
    INTO has_pretty_legacy;

  -- Only rename if legacy names exist and canonical ones do not yet.
  IF has_count_legacy AND NOT has_count_eff THEN
    EXECUTE 'ALTER VIEW public.v_clutch_treatments RENAME COLUMN treatments_count TO treatments_count_effective';
  END IF;

  IF has_pretty_legacy AND NOT has_pretty_eff THEN
    EXECUTE 'ALTER VIEW public.v_clutch_treatments RENAME COLUMN treatments_pretty TO treatments_pretty_effective';
  END IF;
END
$$;

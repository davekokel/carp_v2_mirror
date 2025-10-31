-- 1) Rename existing golden name out of the way (dependents stay attached to its OID)
DO $$
BEGIN
  IF to_regclass('public.v_clutch_instances') IS NOT NULL THEN
    EXECUTE 'ALTER VIEW public.v_clutch_instances RENAME TO v_clutch_instances_legacy';
  END IF;
END $$;

-- 2) Promote resolved view to the golden name
DO $$
BEGIN
  IF to_regclass('public.v_clutch_instances_resolved') IS NOT NULL THEN
    EXECUTE 'ALTER VIEW public.v_clutch_instances_resolved RENAME TO v_clutch_instances';
  ELSE
    RAISE EXCEPTION 'v_clutch_instances_resolved not found';
  END IF;
END $$;

COMMENT ON VIEW public.v_clutch_instances IS
  'Golden clutch instances view: joins v_clutch_treatments; coalesces genotype; canonical names.';
COMMENT ON VIEW public.v_clutch_instances_legacy IS
  'Legacy clutch instances view kept for backward compatibility (will be retired).';

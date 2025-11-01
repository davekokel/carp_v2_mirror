DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.views
    WHERE table_schema='public' AND table_name='v_materials'
  ) THEN
    EXECUTE $v$
      CREATE VIEW public.v_materials AS
      SELECT 'plasmid'::text AS material_type,
             lower(p.code)::text AS material_code,
             p.name::text  AS material_name
      FROM public.plasmids p
    $v$;
  END IF;
END$$;

CREATE OR REPLACE VIEW public.v_clutch_treatments AS
SELECT
  cm.clutch_instance_id,
  COUNT(*)::int AS treatments_count_effective,
  string_agg(
    DISTINCT COALESCE(cm.material_name, vm.material_name, cm.material_code),
    ' + ' ORDER BY COALESCE(cm.material_name, vm.material_name, cm.material_code)
  ) AS treatments_pretty_effective,
  MAX(cm.created_at) AS last_treatment_at
FROM public.clutch_materials cm
LEFT JOIN public.v_materials vm
  ON lower(vm.material_type)=lower(cm.material_type)
 AND lower(vm.material_code)=lower(cm.material_code)
GROUP BY cm.clutch_instance_id;

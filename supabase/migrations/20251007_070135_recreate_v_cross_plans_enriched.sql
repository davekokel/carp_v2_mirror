BEGIN;
DROP VIEW IF EXISTS public.v_cross_plans_enriched;
CREATE VIEW public.v_cross_plans_enriched AS
SELECT
  p.id,
  p.plan_date,
  p.status,
  p.created_by,
  p.note,
  p.created_at,
  p.tank_a_id,
  ca.label AS tank_a_label,
  ca.container_type AS tank_a_type,
  p.tank_b_id,
  cb.label AS tank_b_label,
  cb.container_type AS tank_b_type,
  COALESCE((
    SELECT string_agg(
      format('%s[%s]%s',
             g.transgene_base_code,
             g.allele_number,
             COALESCE(' '||g.zygosity_planned,'')
      ),
      ', ' ORDER BY g.transgene_base_code, g.allele_number
    )
    FROM public.cross_plan_genotype_alleles g
    WHERE g.plan_id = p.id
  ), '') AS genotype_plan,
  COALESCE((
    SELECT string_agg(
      trim(BOTH ' ' FROM concat(t.treatment_name,
                                CASE WHEN t.amount IS NOT NULL THEN ' '||t.amount::text ELSE '' END,
                                CASE WHEN t.units  IS NOT NULL THEN ' '||t.units      ELSE '' END,
                                CASE WHEN t.timing_note IS NOT NULL THEN ' ['||t.timing_note||']' ELSE '' END)),
      ', ' ORDER BY t.treatment_name
    )
    FROM public.cross_plan_treatments t
    WHERE t.plan_id = p.id
  ), '') AS treatments_plan
FROM public.cross_plans p
LEFT JOIN public.containers ca ON ca.id_uuid = p.tank_a_id
LEFT JOIN public.containers cb ON cb.id_uuid = p.tank_b_id;
COMMIT;

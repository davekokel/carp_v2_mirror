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
        SELECT
            STRING_AGG(
                FORMAT(
                    '%s[%s]%s',
                    g.transgene_base_code,
                    g.allele_number,
                    COALESCE(' ' || g.zygosity_planned, '')
                ),
                ', ' ORDER BY g.transgene_base_code, g.allele_number
            )
        FROM public.cross_plan_genotype_alleles AS g
        WHERE g.plan_id = p.id
    ), '') AS genotype_plan,
    COALESCE((
        SELECT
            STRING_AGG(
                TRIM(BOTH ' ' FROM CONCAT(
                    t.treatment_name,
                    CASE WHEN t.amount IS NOT NULL THEN ' ' || t.amount::text ELSE '' END,
                    CASE WHEN t.units IS NOT NULL THEN ' ' || t.units ELSE '' END,
                    CASE WHEN t.timing_note IS NOT NULL THEN ' [' || t.timing_note || ']' ELSE '' END
                )),
                ', ' ORDER BY t.treatment_name
            )
        FROM public.cross_plan_treatments AS t
        WHERE t.plan_id = p.id
    ), '') AS treatments_plan
FROM public.cross_plans AS p
LEFT JOIN public.containers AS ca ON p.tank_a_id = ca.id_uuid
LEFT JOIN public.containers AS cb ON p.tank_b_id = cb.id_uuid;
COMMIT;

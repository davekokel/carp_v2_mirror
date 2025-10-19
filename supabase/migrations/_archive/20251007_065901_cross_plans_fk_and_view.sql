BEGIN;
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='containers'
  ) AND EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='containers' AND column_name='id_uuid'
  ) THEN
    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conname='fk_cross_plans_tank_a_cont' AND conrelid='public.cross_plans'::regclass
    ) THEN
      ALTER TABLE public.cross_plans
        ADD CONSTRAINT fk_cross_plans_tank_a_cont
        FOREIGN KEY (tank_a_id) REFERENCES public.containers(id_uuid) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conname='fk_cross_plans_tank_b_cont' AND conrelid='public.cross_plans'::regclass
    ) THEN
      ALTER TABLE public.cross_plans
        ADD CONSTRAINT fk_cross_plans_tank_b_cont
        FOREIGN KEY (tank_b_id) REFERENCES public.containers(id_uuid) ON DELETE RESTRICT;
    END IF;
  END IF;
END$$;
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='transgene_alleles'
  ) THEN
    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conname='fk_cpga_transgene_allele' AND conrelid='public.cross_plan_genotype_alleles'::regclass
    ) THEN
      ALTER TABLE public.cross_plan_genotype_alleles
        ADD CONSTRAINT fk_cpga_transgene_allele
        FOREIGN KEY (transgene_base_code, allele_number)
        REFERENCES public.transgene_alleles(transgene_base_code, allele_number)
        ON DELETE RESTRICT;
    END IF;
  END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_cross_plans_tank_a ON public.cross_plans (tank_a_id);
CREATE INDEX IF NOT EXISTS idx_cross_plans_tank_b ON public.cross_plans (tank_b_id);

CREATE OR REPLACE VIEW public.v_cross_plans_enriched AS
SELECT
    p.id,
    p.plan_date,
    p.status,
    p.created_by,
    p.note,
    p.created_at,
    p.tank_a_id,
    ca.label AS tank_a_label,
    p.tank_b_id,
    cb.label AS tank_b_label,
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

BEGIN;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'cross_plan_status') THEN
    CREATE TYPE cross_plan_status AS ENUM ('planned','canceled','executed');
  END IF;
END$$;

ALTER TABLE public.containers
  DROP CONSTRAINT IF EXISTS chk_containers_type_allowed,
  ADD CONSTRAINT chk_containers_type_allowed
  CHECK (container_type IN ('inventory_tank','crossing_tank','holding_tank','nursery_tank','petri_dish'));
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='containers')
     AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='containers' AND column_name='id_uuid') THEN

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_cross_plans_tank_a_cont' AND conrelid='public.cross_plans'::regclass) THEN
      ALTER TABLE public.cross_plans
        ADD CONSTRAINT fk_cross_plans_tank_a_cont
        FOREIGN KEY (tank_a_id) REFERENCES public.containers(id_uuid) ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_cross_plans_tank_b_cont' AND conrelid='public.cross_plans'::regclass) THEN
      ALTER TABLE public.cross_plans
        ADD CONSTRAINT fk_cross_plans_tank_b_cont
        FOREIGN KEY (tank_b_id) REFERENCES public.containers(id_uuid) ON DELETE RESTRICT;
    END IF;
  END IF;
END$$;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='transgene_alleles') THEN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_cpga_transgene_allele' AND conrelid='public.cross_plan_genotype_alleles'::regclass) THEN
      ALTER TABLE public.cross_plan_genotype_alleles
        ADD CONSTRAINT fk_cpga_transgene_allele
        FOREIGN KEY (transgene_base_code, allele_number)
        REFERENCES public.transgene_alleles(transgene_base_code, allele_number)
        ON DELETE RESTRICT;
    END IF;
  END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_cross_plans_plan_date ON public.cross_plans(plan_date);
CREATE INDEX IF NOT EXISTS idx_cross_plans_created_by ON public.cross_plans(created_by);
CREATE INDEX IF NOT EXISTS idx_cross_plans_tank_a ON public.cross_plans(tank_a_id);
CREATE INDEX IF NOT EXISTS idx_cross_plans_tank_b ON public.cross_plans(tank_b_id);
CREATE INDEX IF NOT EXISTS idx_cpga_plan ON public.cross_plan_genotype_alleles(plan_id);
CREATE INDEX IF NOT EXISTS idx_cpt_plan ON public.cross_plan_treatments(plan_id);

CREATE OR REPLACE VIEW public.v_containers_crossing_candidates AS
SELECT id_uuid, container_type, label, status, created_by, created_at, note
FROM public.containers
WHERE container_type IN ('inventory_tank','crossing_tank','holding_tank','nursery_tank','petri_dish');

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

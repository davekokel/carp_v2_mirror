BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'cross_plan_status') THEN
    CREATE TYPE cross_plan_status AS ENUM ('planned','canceled','executed');
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS public.cross_plans (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_date     date NOT NULL,
  tank_a_id     uuid NOT NULL REFERENCES public.tanks(id) ON DELETE RESTRICT,
  tank_b_id     uuid NOT NULL REFERENCES public.tanks(id) ON DELETE RESTRICT,
  status        cross_plan_status NOT NULL DEFAULT 'planned',
  created_by    text NOT NULL,
  note          text NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_cross_plans_unique UNIQUE (plan_date, tank_a_id, tank_b_id),
  CONSTRAINT chk_distinct_tanks CHECK (tank_a_id <> tank_b_id)
);

CREATE INDEX IF NOT EXISTS idx_cross_plans_plan_date ON public.cross_plans(plan_date);
CREATE INDEX IF NOT EXISTS idx_cross_plans_created_by ON public.cross_plans(created_by);

CREATE TABLE IF NOT EXISTS public.cross_plan_genotype_alleles (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id              uuid NOT NULL REFERENCES public.cross_plans(id) ON DELETE CASCADE,
  transgene_base_code  text NOT NULL REFERENCES public.transgenes(transgene_base_code) ON DELETE RESTRICT,
  allele_number        integer NOT NULL,
  zygosity_planned     text NULL,
  UNIQUE (plan_id, transgene_base_code, allele_number),
  FOREIGN KEY (transgene_base_code, allele_number)
    REFERENCES public.transgene_alleles(transgene_base_code, allele_number) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_cpga_plan ON public.cross_plan_genotype_alleles(plan_id);

CREATE TABLE IF NOT EXISTS public.cross_plan_treatments (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id       uuid NOT NULL REFERENCES public.cross_plans(id) ON DELETE CASCADE,
  treatment_name text NOT NULL,
  amount        numeric NULL,
  units         text NULL,
  timing_note   text NULL
);

CREATE INDEX IF NOT EXISTS idx_cpt_plan ON public.cross_plan_treatments(plan_id);

COMMIT;

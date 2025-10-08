BEGIN;

-- Add optional parent fish IDs (keep existing tank columns)
ALTER TABLE public.cross_plans
  ADD COLUMN IF NOT EXISTS mother_fish_id uuid NULL REFERENCES public.fish(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS father_fish_id uuid NULL REFERENCES public.fish(id) ON DELETE RESTRICT;

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_cross_plans_mother ON public.cross_plans(mother_fish_id);
CREATE INDEX IF NOT EXISTS idx_cross_plans_father ON public.cross_plans(father_fish_id);

-- Partial uniq on fish-pair per day (only if both fish are set)
CREATE UNIQUE INDEX IF NOT EXISTS uq_cross_plans_day_fishpair
  ON public.cross_plans(plan_date, mother_fish_id, father_fish_id)
  WHERE mother_fish_id IS NOT NULL AND father_fish_id IS NOT NULL;

-- Keep the tank-pair uniqueness *when* both tanks are present
DROP INDEX IF EXISTS uq_cross_plans_unique;
CREATE UNIQUE INDEX IF NOT EXISTS uq_cross_plans_day_tankpair
  ON public.cross_plans(plan_date, tank_a_id, tank_b_id)
  WHERE tank_a_id IS NOT NULL AND tank_b_id IS NOT NULL;

-- Recreate enriched view to include fish if present
DROP VIEW IF EXISTS public.v_cross_plans_enriched;
CREATE VIEW public.v_cross_plans_enriched AS
SELECT
  p.id,
  p.plan_date,
  p.status,
  p.created_by,
  p.note,
  p.created_at,

  -- optional fish
  p.mother_fish_id,
  fm.fish_code AS mother_fish_code,
  p.father_fish_id,
  ff.fish_code AS father_fish_code,

  -- optional tanks
  p.tank_a_id,
  ca.label AS tank_a_label,
  p.tank_b_id,
  cb.label AS tank_b_label,

  -- rolled genotype plan
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

  -- rolled treatments
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
LEFT JOIN public.fish fm ON fm.id = p.mother_fish_id
LEFT JOIN public.fish ff ON ff.id = p.father_fish_id
LEFT JOIN public.containers ca ON ca.id_uuid = p.tank_a_id
LEFT JOIN public.containers cb ON cb.id_uuid = p.tank_b_id;

COMMIT;

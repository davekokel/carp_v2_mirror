BEGIN;

-- 1) Add optional parent fish columns (safe if re-run)
ALTER TABLE public.cross_plans
ADD COLUMN IF NOT EXISTS mother_fish_id uuid NULL REFERENCES public.fish (id) ON DELETE RESTRICT,
ADD COLUMN IF NOT EXISTS father_fish_id uuid NULL REFERENCES public.fish (id) ON DELETE RESTRICT;

-- 2) Helpful non-unique indexes
CREATE INDEX IF NOT EXISTS idx_cross_plans_mother ON public.cross_plans (mother_fish_id);
CREATE INDEX IF NOT EXISTS idx_cross_plans_father ON public.cross_plans (father_fish_id);

-- 3) Recreate enriched view to include parent fish (idempotent)
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

    -- rolled treatments
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
LEFT JOIN public.fish AS fm ON p.mother_fish_id = fm.id
LEFT JOIN public.fish AS ff ON p.father_fish_id = ff.id
LEFT JOIN public.containers AS ca ON p.tank_a_id = ca.id_uuid
LEFT JOIN public.containers AS cb ON p.tank_b_id = cb.id_uuid;

-- 4) Partial unique index for fish-pair by day (now columns exist)
CREATE UNIQUE INDEX IF NOT EXISTS uq_cross_plans_day_fishpair
ON public.cross_plans (plan_date, mother_fish_id, father_fish_id)
WHERE mother_fish_id IS NOT NULL AND father_fish_id IS NOT NULL;

COMMIT;

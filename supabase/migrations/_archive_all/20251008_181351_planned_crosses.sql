BEGIN;

CREATE TABLE IF NOT EXISTS public.planned_crosses (
    id_uuid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clutch_id uuid NOT NULL REFERENCES public.clutch_plans (id_uuid) ON DELETE CASCADE,
    mom_code text NOT NULL,
    dad_code text NOT NULL,
    crossing_tank_id uuid,  -- references containers.id_uuid (crossing_tank)
    cross_date date NOT NULL DEFAULT current_date,
    note text,
    created_by text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_planned_crosses_clutch ON public.planned_crosses (clutch_id);

COMMIT;

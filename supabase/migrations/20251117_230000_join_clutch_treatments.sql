BEGIN;

CREATE TABLE IF NOT EXISTS public.join_clutch_treatments (
    id           uuid PRIMARY KEY,
    clutch_id    uuid NOT NULL REFERENCES public.clutches(id) ON DELETE CASCADE,
    treatment_id uuid NOT NULL REFERENCES public.treatments(id) ON DELETE CASCADE,
    applied_at   timestamp with time zone,
    notes        text,
    created_at   timestamp with time zone DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS join_clutch_treatments_clutch_treatment_idx
    ON public.join_clutch_treatments (clutch_id, treatment_id);

COMMIT;

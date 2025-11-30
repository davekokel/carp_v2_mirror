BEGIN;

DROP TABLE IF EXISTS public.treated_clutches_v11 CASCADE;

CREATE TABLE public.treated_clutches_v11 (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clutch_id           uuid NOT NULL REFERENCES public.clutches(id) ON DELETE CASCADE,
    treated_clutch_code text UNIQUE NOT NULL,
    treatment_id        uuid NOT NULL REFERENCES public.treatments(id),
    n_embryos           integer,
    notes               text,
    created_at          timestamptz DEFAULT now(),
    created_by          text DEFAULT current_user
);

CREATE INDEX idx_treated_clutches_v11_clutch   ON public.treated_clutches_v11(clutch_id);
CREATE INDEX idx_treated_clutches_v11_treat    ON public.treated_clutches_v11(treatment_id);

COMMENT ON TABLE public.treated_clutches_v11 IS
  'Clean v11 table for (clutch × treatment) groupings.';

COMMIT;

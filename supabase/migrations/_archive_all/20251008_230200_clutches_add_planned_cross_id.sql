BEGIN;

ALTER TABLE public.clutches
ADD COLUMN IF NOT EXISTS planned_cross_id uuid REFERENCES public.planned_crosses (id_uuid);

-- Idempotency: one clutch per planned_cross + date (prevents duplicates when 'ensure' is called)
CREATE UNIQUE INDEX IF NOT EXISTS uq_clutches_planned_by_date
ON public.clutches (planned_cross_id, date_birth);

COMMIT;

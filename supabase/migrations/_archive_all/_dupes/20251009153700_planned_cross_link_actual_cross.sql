BEGIN;

-- Add a nullable FK to the actual cross
ALTER TABLE public.planned_crosses
ADD COLUMN IF NOT EXISTS cross_id uuid,
ADD CONSTRAINT planned_crosses_cross_id_fkey
FOREIGN KEY (cross_id) REFERENCES public.crosses (id_uuid) ON DELETE SET NULL;

-- Optional denormalized code for easy display
ALTER TABLE public.planned_crosses
ADD COLUMN IF NOT EXISTS cross_code text;

-- (Optional) keep cross_code unique when present
CREATE UNIQUE INDEX IF NOT EXISTS uq_planned_crosses_cross_code
ON public.planned_crosses (cross_code) WHERE cross_code IS NOT NULL;

COMMIT;

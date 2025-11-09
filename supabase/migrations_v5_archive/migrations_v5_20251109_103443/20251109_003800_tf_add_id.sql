BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
ALTER TABLE public.treatments_fluorescent ADD COLUMN IF NOT EXISTS id uuid DEFAULT gen_random_uuid();
ALTER TABLE public.treatments_fluorescent ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_treatments_fluorescent_id ON public.treatments_fluorescent(id);
COMMIT;

-- Add unique index for ON CONFLICT(idempotency_key)
ALTER TABLE public.cross_instances
  ADD COLUMN IF NOT EXISTS idempotency_key text;

CREATE UNIQUE INDEX IF NOT EXISTS uq_cross_idempotency_key
  ON public.cross_instances(idempotency_key)
  WHERE idempotency_key IS NOT NULL;

COMMENT ON COLUMN public.cross_instances.idempotency_key IS
  'Client-generated UUID for idempotent inserts (to prevent duplicate crosses).';

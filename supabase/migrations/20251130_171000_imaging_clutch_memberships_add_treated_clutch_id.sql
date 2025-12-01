BEGIN;

ALTER TABLE public.imaging_clutch_memberships
  ADD COLUMN IF NOT EXISTS treated_clutch_id uuid;

ALTER TABLE public.imaging_clutch_memberships
  ADD CONSTRAINT imaging_clutch_memberships_treated_clutch_id_fkey
  FOREIGN KEY (treated_clutch_id)
  REFERENCES public.treated_clutches_v11(id)
  ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_imaging_clutch_memberships_treated_clutch_id
  ON public.imaging_clutch_memberships(treated_clutch_id);

COMMIT;

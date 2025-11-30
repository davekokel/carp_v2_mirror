BEGIN;

ALTER TABLE public.imaging_clutch_memberships
  ADD COLUMN IF NOT EXISTS treated_clutch_id uuid;

ALTER TABLE public.imaging_clutch_memberships
  DROP CONSTRAINT IF EXISTS imaging_clutch_memberships_treated_fk;

ALTER TABLE public.imaging_clutch_memberships
  ADD CONSTRAINT imaging_clutch_memberships_treated_fk
    FOREIGN KEY (treated_clutch_id)
    REFERENCES public.treated_clutches_v11(id)
    ON DELETE SET NULL;

COMMENT ON COLUMN public.imaging_clutch_memberships.treated_clutch_id IS
  'Optional FK to treated_clutches_v11.id; records which treated clutch subgroup was mounted into this slot.';

COMMIT;

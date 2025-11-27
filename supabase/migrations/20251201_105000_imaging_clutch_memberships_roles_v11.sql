BEGIN;

-- Restrict role to a known set of values.
-- For now we support: primary, secondary, control, unknown.
ALTER TABLE public.imaging_clutch_memberships
  ADD CONSTRAINT imaging_clutch_memberships_role_chk_v11
  CHECK (
    role IS NULL
    OR lower(trim(role)) IN ('primary', 'secondary', 'control', 'unknown')
  );

-- Indexes to speed up common queries.
CREATE INDEX IF NOT EXISTS imaging_clutch_memberships_clutch_id_idx_v11
  ON public.imaging_clutch_memberships (clutch_id);

CREATE INDEX IF NOT EXISTS imaging_clutch_memberships_slot_id_idx_v11
  ON public.imaging_clutch_memberships (slot_id);

CREATE INDEX IF NOT EXISTS imaging_clutch_memberships_clutch_slot_idx_v11
  ON public.imaging_clutch_memberships (clutch_id, slot_id);

COMMIT;

BEGIN;

----------------------------------------------------------------------
-- v8 canonical imaging_clutch_memberships
-- We drop any legacy version and recreate the ideal design.
----------------------------------------------------------------------

DROP TABLE IF EXISTS public.imaging_clutch_memberships_v8 CASCADE;
DROP TABLE IF EXISTS public.imaging_clutch_memberships CASCADE;

CREATE TABLE public.imaging_clutch_memberships (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_id    uuid NOT NULL REFERENCES public.clutches(id)
                         ON UPDATE CASCADE ON DELETE RESTRICT,
  slot_id      uuid NOT NULL REFERENCES public.imaging_slots(id)
                         ON UPDATE CASCADE ON DELETE RESTRICT,
  role         text DEFAULT 'primary',
  embryo_count integer,
  mount_notes  text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  created_by   text,
  UNIQUE (clutch_id, slot_id)
);

COMMIT;

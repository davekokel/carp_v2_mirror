BEGIN;

----------------------------------------------------------------------
-- v8: imaging_plates + imaging_slots (drop old, recreate ideal)
-- We are in design mode and OK with breaking v7-era tables here.
----------------------------------------------------------------------

-- Drop old versions if they exist
DROP TABLE IF EXISTS public.imaging_slots CASCADE;
DROP TABLE IF EXISTS public.imaging_plates CASCADE;

-- 1. imaging_plates: canonical plate-level metadata
CREATE TABLE public.imaging_plates (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plate_code      text NOT NULL UNIQUE,
  experiment_date date,
  experiment_name text,
  instrument      text,
  format_code     text,
  notes           text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  created_by      text
);

-- 2. imaging_slots: one row per physical mount position on a plate
CREATE TABLE public.imaging_slots (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plate_id    uuid NOT NULL REFERENCES public.imaging_plates(id)
                           ON UPDATE CASCADE ON DELETE RESTRICT,
  slot_index  integer NOT NULL,
  slot_label  text NOT NULL,
  well_row    smallint,
  well_col    smallint,
  notes       text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (plate_id, slot_index),
  UNIQUE (slot_label)
);

-- No legacy backfill here on purpose: v8 will wipe + reload
-- from its own imaging pipelines.

COMMIT;

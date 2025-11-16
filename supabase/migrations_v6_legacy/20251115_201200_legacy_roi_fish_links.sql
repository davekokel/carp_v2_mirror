BEGIN;

CREATE TABLE IF NOT EXISTS public.legacy_roi_fish_links (
  raw_roi_id   uuid NOT NULL,
  parent_role  text NOT NULL,   -- 'mother' or 'father'
  fish_id      uuid NOT NULL,
  fish_code    text NOT NULL,
  source       text NOT NULL DEFAULT 'parent_allele_unique',
  created_at   timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT legacy_roi_fish_links_parent_role_chk
    CHECK (parent_role IN ('mother','father')),

  CONSTRAINT legacy_roi_fish_links_unique
    UNIQUE (raw_roi_id, parent_role)
);

COMMIT;

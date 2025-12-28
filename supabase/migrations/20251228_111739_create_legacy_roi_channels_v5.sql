BEGIN;

CREATE TABLE IF NOT EXISTS public.legacy_roi_channels_v5 (
  roi_path TEXT NOT NULL,
  channel_name TEXT NOT NULL,
  n_tiffs INTEGER NOT NULL CHECK (n_tiffs >= 0),
  decision_status TEXT NOT NULL DEFAULT 'undecided' CHECK (decision_status IN ('keep','kill','undecided')),
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (roi_path, channel_name)
);

COMMIT;

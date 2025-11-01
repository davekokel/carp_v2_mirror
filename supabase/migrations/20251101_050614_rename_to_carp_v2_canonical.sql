-- Rename core tables to the new canonical schema
DO $$
BEGIN
  -- Entities
  IF to_regclass('public.crosses') IS NULL AND to_regclass('public.cross_instances') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.cross_instances RENAME TO crosses';
  END IF;

  IF to_regclass('public.clutches') IS NULL AND to_regclass('public.clutch_instances') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.clutch_instances RENAME TO clutches';
  END IF;

  -- Treatments (generic link for clutches → materials)
  IF to_regclass('public.treatments') IS NULL AND to_regclass('public.clutch_materials') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.clutch_materials RENAME TO treatments';
  END IF;

  -- Joins
  IF to_regclass('public.join_fish_tanks') IS NULL AND to_regclass('public.fish_tank_memberships') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.fish_tank_memberships RENAME TO join_fish_tanks';
  END IF;

  IF to_regclass('public.join_fish_transgene_alleles') IS NULL AND to_regclass('public.fish_transgene_alleles') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.fish_transgene_alleles RENAME TO join_fish_transgene_alleles';
  END IF;

  IF to_regclass('public.join_plasmid_fusions') IS NULL AND to_regclass('public.plasmid_fusions') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.plasmid_fusions RENAME TO join_plasmid_fusions';
  END IF;

  -- Ops / history
  IF to_regclass('public.tank_history') IS NULL AND to_regclass('public.tank_status_history') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.tank_status_history RENAME TO tank_history';
  END IF;
END$$;

-- Label history ledgers (split by domain)
CREATE TABLE IF NOT EXISTS public.tank_label_history (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_id       uuid NOT NULL,
  printed_at    timestamptz NOT NULL DEFAULT now(),
  printed_by    text NOT NULL DEFAULT '',
  label_kind    text NOT NULL DEFAULT 'tank',   -- e.g., tank_label, tank_qr, etc.
  payload_json  jsonb NOT NULL DEFAULT '{}'::jsonb,
  file_uri      text NOT NULL DEFAULT ''        -- where the PDF/asset was written (if any)
);

CREATE INDEX IF NOT EXISTS idx_tank_label_history_tank  ON public.tank_label_history (tank_id);
CREATE INDEX IF NOT EXISTS idx_tank_label_history_time  ON public.tank_label_history (printed_at DESC);

CREATE TABLE IF NOT EXISTS public.cross_label_history (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cross_id       uuid,   -- optional; links to crosses.id if available
  clutch_id      uuid,   -- optional; links to clutches.id if available
  printed_at     timestamptz NOT NULL DEFAULT now(),
  printed_by     text NOT NULL DEFAULT '',
  label_kind     text NOT NULL DEFAULT 'clutch',  -- e.g., cross_label, clutch_label, petri_label
  payload_json   jsonb NOT NULL DEFAULT '{}'::jsonb,
  file_uri       text NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_cross_label_history_cross  ON public.cross_label_history (cross_id);
CREATE INDEX IF NOT EXISTS idx_cross_label_history_clutch ON public.cross_label_history (clutch_id);
CREATE INDEX IF NOT EXISTS idx_cross_label_history_time   ON public.cross_label_history (printed_at DESC);

-- Minimal column guards to keep pages happy when empty DB:
-- Ensure crosses has created_by (nullable) & created_at (if not present already)
DO $$
BEGIN
  IF to_regclass('public.crosses') IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='crosses' AND column_name='created_by'
    ) THEN
      EXECUTE 'ALTER TABLE public.crosses ADD COLUMN created_by text';
    END IF;

    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='crosses' AND column_name='created_at'
    ) THEN
      EXECUTE 'ALTER TABLE public.crosses ADD COLUMN created_at timestamptz NOT NULL DEFAULT now()';
    END IF;
  END IF;
END$$;

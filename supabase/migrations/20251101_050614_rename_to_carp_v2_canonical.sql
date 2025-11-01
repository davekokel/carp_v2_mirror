BEGIN;

-- Idempotent renames from old names to canonical names
DO $$
BEGIN
  IF to_regclass('public.cross_instances') IS NOT NULL
     AND to_regclass('public.crosses') IS NULL THEN
    EXECUTE 'ALTER TABLE public.cross_instances RENAME TO crosses';
  END IF;

  IF to_regclass('public.clutch_instances') IS NOT NULL
     AND to_regclass('public.clutches') IS NULL THEN
    EXECUTE 'ALTER TABLE public.clutch_instances RENAME TO clutches';
  END IF;

  IF to_regclass('public.fish_tank_memberships') IS NOT NULL
     AND to_regclass('public.join_fish_tanks') IS NULL THEN
    EXECUTE 'ALTER TABLE public.fish_tank_memberships RENAME TO join_fish_tanks';
  END IF;

  IF to_regclass('public.fish_transgene_alleles') IS NOT NULL
     AND to_regclass('public.join_fish_transgene_alleles') IS NULL THEN
    EXECUTE 'ALTER TABLE public.fish_transgene_alleles RENAME TO join_fish_transgene_alleles';
  END IF;

  IF to_regclass('public.plasmid_fusions') IS NOT NULL
     AND to_regclass('public.join_plasmid_fusions') IS NULL THEN
    EXECUTE 'ALTER TABLE public.plasmid_fusions RENAME TO join_plasmid_fusions';
  END IF;

  IF to_regclass('public.tank_status_history') IS NOT NULL
     AND to_regclass('public.tank_history') IS NULL THEN
    EXECUTE 'ALTER TABLE public.tank_status_history RENAME TO tank_history';
  END IF;
END $$;

-- Label history tables (create if missing)
CREATE TABLE IF NOT EXISTS public.tank_label_history (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_uuid  uuid,
  label      text,
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by text
);

CREATE TABLE IF NOT EXISTS public.cross_label_history (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cross_id   uuid,
  label      text,
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by text
);

-- Ensure columns on crosses (idempotent)
DO $$
BEGIN
  IF to_regclass('public.crosses') IS NOT NULL THEN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='public' AND table_name='crosses' AND column_name='cross_date') THEN
      EXECUTE 'ALTER TABLE public.crosses ADD COLUMN cross_date date';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='public' AND table_name='crosses' AND column_name='created_by') THEN
      EXECUTE 'ALTER TABLE public.crosses ADD COLUMN created_by text';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='public' AND table_name='crosses' AND column_name='created_at') THEN
      EXECUTE 'ALTER TABLE public.crosses ADD COLUMN created_at timestamptz NOT NULL DEFAULT now()';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='public' AND table_name='crosses' AND column_name='cross_run_code') THEN
      EXECUTE 'ALTER TABLE public.crosses ADD COLUMN cross_run_code text';
    END IF;
  END IF;
END $$;

COMMIT;

-- Prepare v_clutch_treatments for upcoming CREATE OR REPLACE that uses *_effective names.
-- If view exists with legacy names, rename them now so the next migration applies cleanly.

DO $$
BEGIN
  IF to_regclass('public.v_clutch_treatments') IS NOT NULL THEN
    -- rename treatments_count -> treatments_count_effective
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='v_clutch_treatments'
        AND column_name='treatments_count'
    ) AND NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='v_clutch_treatments'
        AND column_name='treatments_count_effective'
    ) THEN
      EXECUTE 'ALTER VIEW public.v_clutch_treatments RENAME COLUMN treatments_count TO treatments_count_effective';
    END IF;

    -- rename treatments_pretty -> treatments_pretty_effective
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='v_clutch_treatments'
        AND column_name='treatments_pretty'
    ) AND NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='v_clutch_treatments'
        AND column_name='treatments_pretty_effective'
    ) THEN
      EXECUTE 'ALTER VIEW public.v_clutch_treatments RENAME COLUMN treatments_pretty TO treatments_pretty_effective';
    END IF;
  END IF;
END
$$;

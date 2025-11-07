BEGIN;

-- If old table exists and new doesn't, rename it
DO $$
BEGIN
  IF to_regclass('public.fluorescent_treatments') IS NOT NULL
     AND to_regclass('public.treatments_fluorescent') IS NULL THEN
    ALTER TABLE public.fluorescent_treatments RENAME TO treatments_fluorescent;
  END IF;
END$$;

-- Ensure canonical table exists
CREATE TABLE IF NOT EXISTS public.treatments_fluorescent (
  ft_code    text PRIMARY KEY,
  ft_text    text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- If both existed, merge then drop the old table
DO $$
BEGIN
  IF to_regclass('public.fluorescent_treatments') IS NOT NULL
     AND to_regclass('public.treatments_fluorescent') IS NOT NULL THEN
    INSERT INTO public.treatments_fluorescent (ft_code, ft_text, created_by, created_at)
    SELECT ft_code, ft_text, created_by, COALESCE(created_at, now())
    FROM public.fluorescent_treatments
    ON CONFLICT (ft_code) DO NOTHING;
    DROP TABLE public.fluorescent_treatments;
  END IF;
END$$;

-- Clean up any leftover view by that name
DROP VIEW IF EXISTS public.fluorescent_treatments CASCADE;

COMMIT;

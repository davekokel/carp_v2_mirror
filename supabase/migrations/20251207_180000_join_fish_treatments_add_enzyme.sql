BEGIN;

DO $$
BEGIN
  IF to_regclass('public.join_fish_treatments_v11') IS NOT NULL THEN
    ALTER TABLE public.join_fish_treatments_v11
      ADD COLUMN IF NOT EXISTS enzyme text;
    COMMENT ON COLUMN public.join_fish_treatments_v11.enzyme IS
      'Injection / delivery enzyme used for this fish_instance ↔ treatment link (e.g. tol2, phiC, meganuclease).';
  END IF;

  IF to_regclass('public.join_fish_treatments') IS NOT NULL THEN
    ALTER TABLE public.join_fish_treatments
      ADD COLUMN IF NOT EXISTS enzyme text;
    COMMENT ON COLUMN public.join_fish_treatments.enzyme IS
      'Injection / delivery enzyme used for this fish_instance ↔ treatment link (e.g. tol2, phiC, meganuclease).';
  END IF;
END $$;

COMMIT;

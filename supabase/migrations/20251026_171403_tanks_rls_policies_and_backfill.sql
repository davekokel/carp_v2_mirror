BEGIN;

-- Enable RLS on tanks if not already, and add permissive policies
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='tanks' AND c.relrowsecurity
  ) THEN
    ALTER TABLE public.tanks ENABLE ROW LEVEL SECURITY;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='public' AND tablename='tanks' AND policyname='tanks_select_all'
  ) THEN
    CREATE POLICY tanks_select_all ON public.tanks
      FOR SELECT USING (true);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='public' AND tablename='tanks' AND policyname='tanks_insert_all'
  ) THEN
    CREATE POLICY tanks_insert_all ON public.tanks
      FOR INSERT WITH CHECK (true);
  END IF;
END$$;

-- Recreate count view (unchanged, legacy code pattern) just to be sure
DROP VIEW IF EXISTS public.v_fish_current_tank_counts;
CREATE VIEW public.v_fish_current_tank_counts AS
SELECT
  f.fish_uuid,
  COALESCE((
    SELECT COUNT(*)
    FROM public.tanks t
    WHERE t.status='active'
      AND t.tank_code LIKE ('TANK('||f.fish_code||')#%')
  ),0)::int AS current_tanks
FROM public.fish f;

-- Backfill: for any fish with NO legacy-coded tank, create #1
INSERT INTO public.tanks(status, tank_code)
SELECT 'active', 'TANK(' || f.fish_code || ')#1'
FROM public.fish f
LEFT JOIN LATERAL (
  SELECT 1 FROM public.tanks t
  WHERE t.tank_code LIKE ('TANK(' || f.fish_code || ')#%')
  LIMIT 1
) has ON true
WHERE has IS NULL;

COMMIT;

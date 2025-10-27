BEGIN;

-- 1) Make fish_auto_tank run with definer rights and a safe search_path
CREATE OR REPLACE FUNCTION public.fish_auto_tank()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_code text;
BEGIN
  v_code := public.make_tank_code_for_fish(NEW.fish_code);
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='_allow_backfill') THEN INSERT INTO public.tanks(status, tank_code) VALUES ('active', v_code); END IF;
  RETURN NEW;
END
$$;

-- Ensure the function owner is the table owner so SECURITY DEFINER has perms
ALTER FUNCTION public.fish_auto_tank() OWNER TO CURRENT_USER;

-- Recreate the trigger (idempotent)
DROP TRIGGER IF EXISTS trg_fish_auto_tank ON public.fish;
CREATE TRIGGER trg_fish_auto_tank
AFTER INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.fish_auto_tank();

-- 2) Optional: if fish has RLS and you want psql (current role) to SEE rows locally,
-- open a permissive SELECT policy for local dev only. Safe if RLS is not enabled.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='fish')
     AND EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                 WHERE n.nspname='public' AND c.relname='fish' AND c.relrowsecurity) THEN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='fish' AND policyname='fish_local_select_all') THEN
      CREATE POLICY fish_local_select_all ON public.fish FOR SELECT USING (true);
    END IF;
  END IF;
END$$;

-- 3) Backfill any fish that still lack a legacy-coded tank
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

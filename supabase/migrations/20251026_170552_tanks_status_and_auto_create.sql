BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='tank_status') THEN
    CREATE TYPE public.tank_status AS ENUM ('active','to_kill','retired');
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tanks' AND column_name='status'
  ) THEN
    ALTER TABLE public.tanks ADD COLUMN status public.tank_status;
  END IF;
END$$;

UPDATE public.tanks SET status='active' WHERE status IS NULL;
ALTER TABLE public.tanks ALTER COLUMN status SET NOT NULL;
ALTER TABLE public.tanks ALTER COLUMN status SET DEFAULT 'active';

CREATE OR REPLACE FUNCTION public.fish_auto_tank()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_tank_uuid uuid;
BEGIN
  IF EXISTS (SELECT 1 FROM public.fish_tank_memberships m WHERE m.fish_uuid = NEW.fish_uuid) THEN
    RETURN NEW;
  END IF;

  INSERT INTO public.tanks(status) VALUES ('active') RETURNING tank_uuid INTO v_tank_uuid;

  INSERT INTO public.fish_tank_memberships(fish_uuid, tank_uuid)
  VALUES (NEW.fish_uuid, v_tank_uuid)
  ON CONFLICT DO NOTHING;

  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_fish_auto_tank ON public.fish;
CREATE TRIGGER trg_fish_auto_tank
AFTER INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.fish_auto_tank();

CREATE OR REPLACE VIEW public.v_fish_current_tank_counts AS
SELECT
  f.fish_uuid,
  COALESCE(COUNT(*) FILTER (WHERE t.status='active'), 0)::int AS current_tanks
FROM public.fish f
LEFT JOIN public.fish_tank_memberships m ON m.fish_uuid = f.fish_uuid
LEFT JOIN public.tanks t ON t.tank_uuid = m.tank_uuid
GROUP BY f.fish_uuid;

DO $$
DECLARE
  r record;
  v_tank_uuid uuid;
BEGIN
  FOR r IN
    SELECT f.fish_uuid
    FROM public.fish f
    LEFT JOIN public.fish_tank_memberships m ON m.fish_uuid = f.fish_uuid
    WHERE m.fish_uuid IS NULL
  LOOP
    INSERT INTO public.tanks(status) VALUES ('active') RETURNING tank_uuid INTO v_tank_uuid;
    INSERT INTO public.fish_tank_memberships(fish_uuid, tank_uuid)
    VALUES (r.fish_uuid, v_tank_uuid)
    ON CONFLICT DO NOTHING;
  END LOOP;
END
$$;

COMMIT;

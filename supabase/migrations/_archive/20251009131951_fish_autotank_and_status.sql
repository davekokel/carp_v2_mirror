BEGIN;
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'containers_status_check'
      AND conrelid = 'public.containers'::regclass
  ) THEN
    EXECUTE 'ALTER TABLE public.containers DROP CONSTRAINT containers_status_check';
  END IF;
END $$;

ALTER TABLE public.containers
  ADD CONSTRAINT containers_status_check
  CHECK (status IN ('planned','new_tank','active','ready_to_kill','inactive'));

CREATE OR REPLACE FUNCTION public.trg_fish_autotank()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_container_id uuid;
  v_label text;
BEGIN
  v_label := CASE
               WHEN NEW.fish_code IS NOT NULL THEN format('TANK %s #1', NEW.fish_code)
               ELSE NULL
             END;

  INSERT INTO public.containers (container_type, status, label, created_by)
  VALUES ('holding_tank', 'new_tank', v_label, COALESCE(NEW.created_by, 'system'))
  RETURNING id_uuid INTO v_container_id;

  BEGIN
    INSERT INTO public.fish_tank_memberships (fish_id, container_id, started_at)
    VALUES (NEW.id_uuid, v_container_id, now());
  EXCEPTION WHEN undefined_column THEN
    INSERT INTO public.fish_tank_memberships (fish_id, container_id, joined_at)
    VALUES (NEW.id_uuid, v_container_id, now());
  END;

  RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_fish_autotank ON public.fish;
CREATE TRIGGER trg_fish_autotank
AFTER INSERT ON public.fish
FOR EACH ROW EXECUTE FUNCTION public.trg_fish_autotank();

CREATE OR REPLACE FUNCTION public.trg_containers_activate_on_label()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
BEGIN
  IF TG_OP = 'UPDATE'
     AND OLD.status = 'new_tank'
     AND NEW.label IS NOT NULL
     AND NEW.label IS DISTINCT FROM OLD.label THEN
    NEW.status := 'active';
    NEW.status_changed_at := now();
  END IF;
  RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_containers_activate_on_label ON public.containers;
CREATE TRIGGER trg_containers_activate_on_label
BEFORE UPDATE OF label ON public.containers
FOR EACH ROW EXECUTE FUNCTION public.trg_containers_activate_on_label();

COMMIT;

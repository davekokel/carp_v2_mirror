BEGIN;

-- Generate: TANK <FISH_CODE> #<n>
CREATE OR REPLACE FUNCTION public.gen_tank_code_for_fish(p_fish_code text)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
  next_n int;
BEGIN
  -- Find the max trailing number for this fish's tanks: 'TANK <FISH_CODE> #<n>'
  SELECT COALESCE(MAX( (substring(tank_code FROM '#([0-9]+)$'))::int ), 0) + 1
  INTO next_n
  FROM public.containers
  WHERE tank_code LIKE ('TANK ' || p_fish_code || ' #%');

  RETURN 'TANK ' || p_fish_code || ' #' || next_n;
END
$$;

-- Idempotent uniqueness guard (tank_code must be unique when present)
CREATE UNIQUE INDEX IF NOT EXISTS uq_containers_tank_code
  ON public.containers(tank_code)
  WHERE tank_code IS NOT NULL;

-- Recreate fish auto-tank trigger function to assign per-fish tank codes
CREATE OR REPLACE FUNCTION public.trg_fish_autotank()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_label text := COALESCE(NEW.nickname, NEW.name, 'Holding Tank');
  v_container_id uuid;
  v_code text;
BEGIN
  -- Derive the tank_code from this fish's code
  v_code := public.gen_tank_code_for_fish(NEW.fish_code);

  -- Create holding tank with per-fish code
  INSERT INTO public.containers (container_type, status, label, tank_code, created_by)
  VALUES ('holding_tank', 'new_tank', v_label, v_code, COALESCE(NEW.created_by, 'system'))
  RETURNING id INTO v_container_id;

  -- Link fish → tank (handle schema variants)
  BEGIN
    INSERT INTO public.fish_tank_memberships (fish_id, container_id, started_at)
    VALUES (NEW.id, v_container_id, now());
  EXCEPTION WHEN undefined_column THEN
    INSERT INTO public.fish_tank_memberships (fish_id, container_id, joined_at)
    VALUES (NEW.id, v_container_id, now());
  END;

  RETURN NEW;
END
$$;

-- Ensure trigger is attached
DROP TRIGGER IF EXISTS bi_fish_autotank ON public.fish;
CREATE TRIGGER bi_fish_autotank
  AFTER INSERT ON public.fish
  FOR EACH ROW
  EXECUTE FUNCTION public.trg_fish_autotank();

COMMIT;

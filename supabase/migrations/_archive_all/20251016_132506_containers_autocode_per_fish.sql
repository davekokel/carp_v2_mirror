begin;

-- Generate: TANK <FISH_CODE> #<n>
create or replace function public.gen_tank_code_for_fish(p_fish_code text)
returns text
language plpgsql
as $$
DECLARE
  next_n int;
BEGIN
  -- Find the max trailing number for this fish's tanks: 'TANK <FISH_CODE> #<n>'
  SELECT COALESCE(MAX( (substring(tank_code FROM '#([0-9]+)$'))::int ), 0) + 1
  INTO next_n
  FROM public.containers  WHERE tank_code LIKE ('TANK ' || p_fish_code || ' #%');

  RETURN 'TANK ' || p_fish_code || ' #' || next_n;
END
$$;

-- Idempotent uniqueness guard (tank_code must be unique when present)
create unique index if not exists uq_containers_tank_code
on public.containers (tank_code)
where tank_code is not NULL;

-- Recreate fish auto-tank trigger function to assign per-fish tank codes
create or replace function public.trg_fish_autotank()
returns trigger
language plpgsql
as $$
DECLARE
  v_label text := COALESCE(NEW.nickname, NEW.name, 'Holding Tank');
  v_container_id uuid;
  v_code text;
BEGIN
  -- Derive the tank_code from this AS fish's code
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
drop trigger if exists bi_fish_autotank on public.fish;
create trigger bi_fish_autotank
after insert on public.fish
for each row
execute function public.trg_fish_autotank();

commit;

-- 1) Ensure the helper columns exist (idempotent safety)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish_tank_memberships' AND column_name='left_at'
  ) THEN
    ALTER TABLE public.fish_tank_memberships ADD COLUMN left_at timestamptz;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish_tank_memberships' AND column_name='joined_at'
  ) THEN
    ALTER TABLE public.fish_tank_memberships ADD COLUMN joined_at timestamptz DEFAULT now();
  END IF;
END$$;

-- 2) Authoritative function: ensure active tank + open membership
CREATE OR REPLACE FUNCTION public.ensure_active_tank_for_fish(p_fish_code text)
RETURNS void
LANGUAGE plpgsql
SET search_path = public
AS $fn$
DECLARE
  v_fish_uuid uuid;
  v_tank_uuid uuid;
  v_num int;
  v_tank_code text;
BEGIN
  -- Find fish
  SELECT fish_uuid INTO v_fish_uuid
  FROM public.fish
  WHERE fish_code = p_fish_code
  LIMIT 1;

  IF v_fish_uuid IS NULL THEN
    RAISE EXCEPTION 'ensure_active_tank_for_fish(): fish_code % not found', p_fish_code;
  END IF;

  -- Try to find an existing active tank for this fish code
  SELECT t.tank_uuid
    INTO v_tank_uuid
  FROM public.tanks t
  WHERE t.status = 'active'
    AND t.tank_code LIKE ('TANK(' || p_fish_code || ')#%')
  ORDER BY t.created_at ASC
  LIMIT 1;

  -- If none, create one deterministically as next #N
  IF v_tank_uuid IS NULL THEN
    SELECT COALESCE(MAX(NULLIF(split_part(tank_code, '#', 2), '')::int), 0) + 1
      INTO v_num
    FROM public.tanks
    WHERE tank_code LIKE ('TANK(' || p_fish_code || ')#%');

    v_tank_code := 'TANK(' || p_fish_code || ')#' || v_num::text;

    INSERT INTO public.tanks (tank_uuid, tank_code, status, created_at)
    VALUES (gen_random_uuid(), v_tank_code, 'active', now())
    RETURNING tank_uuid INTO v_tank_uuid;
  END IF;

  -- Close any other open memberships for this fish
  UPDATE public.fish_tank_memberships m
  SET left_at = now()
  WHERE m.fish_uuid = v_fish_uuid
    AND m.left_at IS NULL
    AND m.tank_uuid <> v_tank_uuid;

  -- Ensure an open membership exists for (fish, v_tank_uuid)
  IF NOT EXISTS (
    SELECT 1 FROM public.fish_tank_memberships m
    WHERE m.fish_uuid = v_fish_uuid
      AND m.tank_uuid = v_tank_uuid
      AND m.left_at IS NULL
  ) THEN
    INSERT INTO public.fish_tank_memberships (fish_uuid, tank_uuid, joined_at)
    VALUES (v_fish_uuid, v_tank_uuid, now());
  END IF;
END
$fn$;

-- 3) Backfill: for any fish with an active TANK(<code>)#? that lacks an open membership, create it.
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT f.fish_uuid, t.tank_uuid
    FROM public.fish f
    JOIN public.tanks t
      ON t.status = 'active'
     AND t.tank_code LIKE ('TANK(' || f.fish_code || ')#%')
    LEFT JOIN public.fish_tank_memberships m
      ON m.fish_uuid = f.fish_uuid
     AND m.tank_uuid = t.tank_uuid
     AND m.left_at IS NULL
    WHERE m.fish_uuid IS NULL
  LOOP
    -- close any other open memberships
    UPDATE public.fish_tank_memberships
    SET left_at = now()
    WHERE fish_uuid = r.fish_uuid AND left_at IS NULL AND tank_uuid <> r.tank_uuid;

    -- open the missing one
    INSERT INTO public.fish_tank_memberships (fish_uuid, tank_uuid, joined_at)
    VALUES (r.fish_uuid, r.tank_uuid, now());
  END LOOP;
END$$;

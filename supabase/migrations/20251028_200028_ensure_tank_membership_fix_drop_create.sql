BEGIN;

DROP FUNCTION IF EXISTS public.ensure_active_tank_for_fish(text);

CREATE FUNCTION public.ensure_active_tank_for_fish(p_fish_code text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
  v_fish_uuid  uuid;
  v_tank_uuid  uuid;
  v_next_num   int;
  v_tank_code  text;
BEGIN
  SELECT fish_uuid INTO v_fish_uuid
  FROM public.fish
  WHERE fish_code = p_fish_code
  LIMIT 1;

  IF v_fish_uuid IS NULL THEN
    RAISE EXCEPTION 'ensure_active_tank_for_fish(): fish_code % not found', p_fish_code;
  END IF;

  SELECT t.tank_uuid
    INTO v_tank_uuid
  FROM public.tanks t
  WHERE t.status = 'active'
    AND t.tank_code LIKE ('TANK(' || p_fish_code || ')#%')
  ORDER BY t.created_at ASC
  LIMIT 1;

  IF v_tank_uuid IS NULL THEN
    SELECT COALESCE(MAX(NULLIF(split_part(tank_code, '#', 2), '')::int), 0) + 1
      INTO v_next_num
    FROM public.tanks
    WHERE tank_code LIKE ('TANK(' || p_fish_code || ')#%');

    v_tank_code := 'TANK(' || p_fish_code || ')#' || v_next_num::text;

    INSERT INTO public.tanks (tank_uuid, tank_code, status, created_at)
    VALUES (gen_random_uuid(), v_tank_code, 'active', now())
    RETURNING tank_uuid INTO v_tank_uuid;
  END IF;

  UPDATE public.fish_tank_memberships
     SET left_at = now()
   WHERE fish_uuid = v_fish_uuid
     AND left_at IS NULL
     AND tank_uuid <> v_tank_uuid;

  IF NOT EXISTS (
    SELECT 1
      FROM public.fish_tank_memberships m
     WHERE m.fish_uuid = v_fish_uuid
       AND m.tank_uuid = v_tank_uuid
       AND m.left_at IS NULL
  ) THEN
    INSERT INTO public.fish_tank_memberships (fish_uuid, tank_uuid, joined_at)
    VALUES (v_fish_uuid, v_tank_uuid, now());
  END IF;
END
$fn$;

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
    UPDATE public.fish_tank_memberships
       SET left_at = now()
     WHERE fish_uuid = r.fish_uuid
       AND left_at IS NULL
       AND tank_uuid <> r.tank_uuid;

    INSERT INTO public.fish_tank_memberships (fish_uuid, tank_uuid, joined_at)
    VALUES (r.fish_uuid, r.tank_uuid, now());
  END LOOP;
END$$;

COMMIT;

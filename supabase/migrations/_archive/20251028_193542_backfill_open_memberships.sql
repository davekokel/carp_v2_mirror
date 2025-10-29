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
     WHERE fish_uuid = r.fish_uuid
       AND left_at IS NULL
       AND tank_uuid <> r.tank_uuid;

    -- open the missing membership
    INSERT INTO public.fish_tank_memberships (fish_uuid, tank_uuid, joined_at)
    VALUES (r.fish_uuid, r.tank_uuid, now());
  END LOOP;
END$$;

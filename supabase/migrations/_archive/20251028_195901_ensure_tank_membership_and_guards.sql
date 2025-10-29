BEGIN;

-- 0) indexes / invariants for membership lookups
CREATE UNIQUE INDEX IF NOT EXISTS uq_ftm_one_open_per_fish
  ON public.fish_tank_memberships(fish_uuid)
  WHERE left_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_ftm_fish_open
  ON public.fish_tank_memberships(fish_uuid)
  WHERE left_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_ftm_tank_open
  ON public.fish_tank_memberships(tank_uuid)
  WHERE left_at IS NULL;

-- 1) authoritative function: ensure active tank + one open membership
CREATE OR REPLACE FUNCTION public.ensure_active_tank_for_fish(p_fish_code text)
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

  -- find existing active tank for this code
  SELECT t.tank_uuid
    INTO v_tank_uuid
  FROM public.tanks t
  WHERE t.status = 'active'
    AND t.tank_code LIKE ('TANK(' || p_fish_code || ')#%')
  ORDER BY t.created_at ASC
  LIMIT 1;

  -- create next TANK(<code>)#N if none
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

  -- close any other open memberships for this fish
  UPDATE public.fish_tank_memberships m
     SET left_at = now()
   WHERE m.fish_uuid = v_fish_uuid
     AND m.left_at IS NULL
     AND m.tank_uuid <> v_tank_uuid;

  -- ensure an open membership exists for (fish, v_tank_uuid)
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

-- 2) backfill open memberships for existing active TANK(<code>)#N tanks
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
    -- close any other open memberships for this fish
    UPDATE public.fish_tank_memberships
       SET left_at = now()
     WHERE fish_uuid = r.fish_uuid
       AND left_at IS NULL
       AND tank_uuid <> r.tank_uuid;

    -- open one membership
    INSERT INTO public.fish_tank_memberships (fish_uuid, tank_uuid, joined_at)
    VALUES (r.fish_uuid, r.tank_uuid, now());
  END LOOP;
END$$;

-- 3) guardrails / assertions (fail rebuild if violated)

-- a) there should be only ONE upsert overload
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n
  FROM pg_proc p
  JOIN pg_namespace nsp ON nsp.oid = p.pronamespace
  WHERE nsp.nspname='public'
    AND p.proname='upsert_fish_by_batch_name_dob';
  IF n <> 1 THEN
    RAISE EXCEPTION 'Guard: expected 1 overload of upsert_fish_by_batch_name_dob, found %', n;
  END IF;
END$$;

-- b) zero or one open membership per fish is enforced by uq_ftm_one_open_per_fish,
--    but check quickly for any existing violation (should be none)
DO $$
DECLARE bad int;
BEGIN
  SELECT COUNT(*) INTO bad
  FROM (
    SELECT fish_uuid, COUNT(*) AS c
    FROM public.fish_tank_memberships
    WHERE left_at IS NULL
    GROUP BY fish_uuid
    HAVING COUNT(*) > 1
  ) s;
  IF bad > 0 THEN
    RAISE EXCEPTION 'Guard: found % fish with multiple open memberships', bad;
  END IF;
END$$;

COMMIT;

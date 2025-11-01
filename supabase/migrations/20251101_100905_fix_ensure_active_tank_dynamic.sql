BEGIN;

-- Replace the function with a dynamic-SQL version that adapts to your join/tank columns
DROP FUNCTION IF EXISTS public.ensure_active_tank_for_fish(text);

CREATE FUNCTION public.ensure_active_tank_for_fish(p_fish_code text)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
  v_code       text := NULLIF(btrim(coalesce(p_fish_code,'')), '');
  v_tank_code  text;
  v_fish_id    uuid;

  -- join_fish_tanks column presence
  has_fish_uuid boolean;
  has_fish_id   boolean;
  has_fish_code boolean;
  has_tank_uuid boolean;
  has_tank_id   boolean;
  has_tank_code boolean;

  fish_col_name text;   -- chosen fish column name in join_fish_tanks (if any)
  tank_col_name text;   -- chosen tank column name in join_fish_tanks (if any)

  tanks_has_code boolean;

  exists_sql text;
  exists_any boolean;
  ins_sql    text;
BEGIN
  IF v_code IS NULL THEN
    RAISE EXCEPTION 'fish_code required';
  END IF;

  SELECT id INTO v_fish_id FROM public.fish WHERE fish_code = v_code LIMIT 1;
  IF v_fish_id IS NULL THEN
    RAISE EXCEPTION 'fish_code % not found', v_code;
  END IF;

  v_tank_code := format('TANK(%s)#1', v_code);

  -- Ensure tank exists by code when possible
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tanks' AND column_name='tank_code'
  ) INTO tanks_has_code;

  IF tanks_has_code THEN
    IF NOT EXISTS (SELECT 1 FROM public.tanks WHERE tank_code = v_tank_code) THEN
      INSERT INTO public.tanks(tank_code) VALUES (v_tank_code);
    END IF;
  END IF;

  -- Detect join_fish_tanks shape
  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='fish_uuid') INTO has_fish_uuid;
  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='fish_id')   INTO has_fish_id;
  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='fish_code') INTO has_fish_code;

  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='tank_uuid') INTO has_tank_uuid;
  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='tank_id')   INTO has_tank_id;
  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='tank_code') INTO has_tank_code;

  -- Choose column names for dynamic SQL
  IF has_fish_uuid THEN
    fish_col_name := 'fish_uuid';
  ELSIF has_fish_id THEN
    fish_col_name := 'fish_id';
  ELSIF has_fish_code THEN
    fish_col_name := 'fish_code';
  ELSE
    RAISE EXCEPTION 'join_fish_tanks must have one of fish_uuid, fish_id, fish_code';
  END IF;

  IF has_tank_code THEN
    tank_col_name := 'tank_code';
  ELSIF has_tank_id THEN
    tank_col_name := 'tank_id';
  ELSIF has_tank_uuid THEN
    tank_col_name := 'tank_uuid';
  ELSE
    RAISE EXCEPTION 'join_fish_tanks must have one of tank_code, tank_id, tank_uuid';
  END IF;

  -- Build an existence check suited to chosen columns
  IF fish_col_name IN ('fish_uuid', 'fish_id') AND tank_col_name = 'tank_code' THEN
    exists_sql := format(
      'SELECT EXISTS (SELECT 1 FROM public.join_fish_tanks j WHERE j.%I = %L AND j.tank_code = %L)',
      fish_col_name, v_fish_id, v_tank_code
    );
  ELSIF fish_col_name IN ('fish_uuid', 'fish_id') AND tank_col_name IN ('tank_id','tank_uuid') THEN
    exists_sql := format(
      'SELECT EXISTS (
         SELECT 1 FROM public.join_fish_tanks j
         WHERE j.%I = %L
           AND j.%I IN (SELECT id FROM public.tanks WHERE tank_code=%L)
       )', fish_col_name, v_fish_id, tank_col_name, v_tank_code
    );
  ELSIF fish_col_name='fish_code' AND tank_col_name='tank_code' THEN
    exists_sql := format(
      'SELECT EXISTS (SELECT 1 FROM public.join_fish_tanks j WHERE j.fish_code=%L AND j.tank_code=%L)',
      v_code, v_tank_code
    );
  ELSIF fish_col_name='fish_code' AND tank_col_name IN ('tank_id','tank_uuid') THEN
    exists_sql := format(
      'SELECT EXISTS (
         SELECT 1 FROM public.join_fish_tanks j
         WHERE j.fish_code = %L
           AND j.%I IN (SELECT id FROM public.tanks WHERE tank_code=%L)
       )', v_code, tank_col_name, v_tank_code
    );
  END IF;

  EXECUTE exists_sql INTO exists_any;
  IF NOT exists_any THEN
    -- Build INSERT suited to available columns
    IF fish_col_name='fish_code' AND tank_col_name='tank_code' THEN
      ins_sql := format(
        'INSERT INTO public.join_fish_tanks(fish_code, tank_code) VALUES (%L, %L)',
        v_code, v_tank_code
      );
    ELSIF fish_col_name IN ('fish_uuid','fish_id') AND tank_col_name='tank_code' THEN
      ins_sql := format(
        'INSERT INTO public.join_fish_tanks(%I, tank_code) VALUES (%L, %L)',
        fish_col_name, v_fish_id, v_tank_code
      );
    ELSIF fish_col_name IN ('fish_uuid','fish_id') AND tank_col_name IN ('tank_id','tank_uuid') THEN
      ins_sql := format(
        'INSERT INTO public.join_fish_tanks(%I, %I)
         SELECT %L, id FROM public.tanks WHERE tank_code=%L LIMIT 1',
        fish_col_name, tank_col_name, v_fish_id, v_tank_code
      );
    ELSIF fish_col_name='fish_code' AND tank_col_name IN ('tank_id','tank_uuid') THEN
      ins_sql := format(
        'INSERT INTO public.join_fish_tanks(fish_code, %I)
         SELECT %L, id FROM public.tanks WHERE tank_code=%L LIMIT 1',
        tank_col_name, v_code, v_tank_code
      );
    END IF;

    EXECUTE ins_sql;
  END IF;

  RETURN v_tank_code;
END;
$$;

COMMIT;

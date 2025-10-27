BEGIN;

DO $do$
DECLARE
  fish_col text;
  tank_pk_col text;
  m_fish_col text;
  m_tank_col text;
  v_tank uuid;
  r record;
BEGIN
  -- Detect fish PK
  SELECT column_name INTO fish_col
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='fish'
    AND column_name IN ('fish_uuid','id','id_uuid')
  ORDER BY CASE column_name WHEN 'fish_uuid' THEN 1 WHEN 'id' THEN 2 WHEN 'id_uuid' THEN 3 ELSE 9 END
  LIMIT 1;

  IF fish_col IS NULL THEN
    RAISE EXCEPTION 'Cannot find fish PK column';
  END IF;

  -- Detect tanks PK
  SELECT column_name INTO tank_pk_col
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='tanks'
    AND column_name IN ('tank_uuid','id')
  ORDER BY CASE column_name WHEN 'tank_uuid' THEN 1 WHEN 'id' THEN 2 ELSE 9 END
  LIMIT 1;

  IF tank_pk_col IS NULL THEN
    RAISE EXCEPTION 'Cannot find tanks PK column';
  END IF;

  -- Detect membership columns
  SELECT max(CASE WHEN column_name IN ('fish_uuid','fish_id') THEN column_name END),
         max(CASE WHEN column_name IN ('tank_uuid','tank_id') THEN column_name END)
    INTO m_fish_col, m_tank_col
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='fish_tank_memberships';

  IF m_fish_col IS NULL OR m_tank_col IS NULL THEN
    RAISE EXCEPTION 'Missing fish_tank_memberships columns (found: %, %)', m_fish_col, m_tank_col;
  END IF;

  -- Backfill: for each fish with no membership, create a tank and membership
  FOR r IN EXECUTE format($q$
        SELECT f.%I AS fish_pk
        FROM public.fish f
        LEFT JOIN public.fish_tank_memberships m
          ON m.%I = f.%I
        WHERE m.%I IS NULL
      $q$, fish_col, m_fish_col, fish_col, m_fish_col)
  LOOP
    -- create a tank row
    EXECUTE format('INSERT INTO public.tanks DEFAULT VALUES RETURNING %I', tank_pk_col)
      INTO v_tank;

    -- link membership
    IF m_tank_col = 'tank_uuid' THEN
      EXECUTE format('INSERT INTO public.fish_tank_memberships(%I, %I) VALUES ($1, $2) ON CONFLICT DO NOTHING', m_fish_col, m_tank_col)
        USING r.fish_pk, v_tank;
    ELSE
      -- if tanks PK is integer id, v_tank::uuid won’t work; fetch the just-created integer
      -- re-select the last inserted tank PK (safe in this xact)
      EXECUTE format('SELECT %I FROM public.tanks ORDER BY ctid DESC LIMIT 1', tank_pk_col) INTO v_tank;
      EXECUTE format('INSERT INTO public.fish_tank_memberships(%I, %I) VALUES ($1, $2) ON CONFLICT DO NOTHING', m_fish_col, m_tank_col)
        USING r.fish_pk, v_tank;
    END IF;
  END LOOP;
END
$do$;

COMMIT;

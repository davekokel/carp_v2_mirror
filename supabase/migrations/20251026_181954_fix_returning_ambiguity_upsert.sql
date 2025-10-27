DROP FUNCTION IF EXISTS public.upsert_fish_by_batch_name_dob(
  text, text, date, text, text, text, text, text, text
);

CREATE FUNCTION public.upsert_fish_by_batch_name_dob(
    p_seed_batch_id text,
    p_name text,
    p_date_birth date,
    p_genetic_background text,
    p_nickname text,
    p_line_building_stage text,
    p_description text,
    p_notes text,
    p_created_by text
)
RETURNS TABLE(fish_uuid uuid, fish_code text)
LANGUAGE plpgsql
AS $$
DECLARE
  v_key text;
  v_join_rhs text;
  v_fu uuid;
  v_fc text;
  v_sql text;
BEGIN
  SELECT CASE
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='fish_seed_batches_map' AND column_name='fish_uuid') THEN 'fish_uuid'
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='fish_seed_batches_map' AND column_name='fish_id')   THEN 'fish_id'
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='fish_seed_batches_map' AND column_name='fish_code') THEN 'fish_code'
           ELSE NULL
         END
  INTO v_key;

  IF v_key IS NULL THEN
    RAISE EXCEPTION 'fish_seed_batches_map missing fish reference column (need one of fish_uuid, fish_id, fish_code)';
  END IF;

  v_join_rhs := CASE WHEN v_key = 'fish_code' THEN 'f.fish_code' ELSE 'f.fish_uuid' END;

  v_sql := format($Q$
      SELECT f.fish_uuid, f.fish_code
      FROM public.fish f
      JOIN public.fish_seed_batches_map m
        ON m.%I = %s
       AND m.seed_batch_id = $3
      WHERE f.name = $1
        AND f.date_birth = $2
      LIMIT 1
    $Q$, v_key, v_join_rhs);

  EXECUTE v_sql USING p_name, p_date_birth, p_seed_batch_id INTO v_fu, v_fc;

  IF v_fu IS NULL THEN
    INSERT INTO public.fish (
      fish_code,
      genetic_background,
      line_building_stage,
      date_birth,
      nickname,
      description,
      notes,
      created_by
    )
    VALUES (
      public.gen_fish_code(),
      p_genetic_background,
      p_line_building_stage,
      p_date_birth,
      p_nickname,
      p_description,
      p_notes,
      p_created_by
    )
    -- Qualify RETURNING to avoid ambiguity with OUT params
    RETURNING public.fish.fish_uuid, public.fish.fish_code
    INTO v_fu, v_fc;

    v_sql := format('INSERT INTO public.fish_seed_batches_map(%I, seed_batch_id) VALUES ($1, $2) ON CONFLICT DO NOTHING', v_key);
    IF v_key = 'fish_code' THEN
      EXECUTE v_sql USING v_fc, p_seed_batch_id;
    ELSE
      EXECUTE v_sql USING v_fu, p_seed_batch_id;
    END IF;
  END IF;

  fish_uuid := v_fu;
  fish_code := v_fc;
  RETURN NEXT;
END
$$;

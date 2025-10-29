DROP FUNCTION IF EXISTS public.upsert_fish_by_batch_name_dob(text,text,date,text,text,text,text,text,text);

CREATE FUNCTION public.upsert_fish_by_batch_name_dob(
    p_seed_batch_id text,
    p_name          text,
    p_date_birth    date,
    p_genetic_background text,
    p_nickname      text,
    p_line_building_stage text,
    p_description   text,
    p_notes         text,
    p_created_by    text
)
RETURNS TABLE(fish_uuid uuid, fish_code text)
LANGUAGE plpgsql
AS $func$
DECLARE
  v_name_norm text := lower(trim(COALESCE(p_name,'')));
  v_fu uuid;
  v_fc text;
BEGIN
  -- A) in-batch via mapping (uuid)
  SELECT f.fish_uuid, f.fish_code
    INTO v_fu, v_fc
  FROM public.fish f
  JOIN public.fish_seed_batches_map m
    ON m.fish_uuid = f.fish_uuid
   AND m.seed_batch_id = p_seed_batch_id
  WHERE lower(trim(COALESCE(f.name,''))) = v_name_norm
    AND f.date_birth = p_date_birth
  LIMIT 1;

  -- B) global reuse by (name_norm, dob, background)
  IF v_fu IS NULL THEN
    SELECT f.fish_uuid, f.fish_code
      INTO v_fu, v_fc
    FROM public.fish f
    WHERE lower(trim(COALESCE(f.name,''))) = v_name_norm
      AND f.date_birth = p_date_birth
      AND COALESCE(f.genetic_background,'') = COALESCE(p_genetic_background,'')
    LIMIT 1;
  END IF;

  -- C) create new if still not found
  IF v_fu IS NULL THEN
    INSERT INTO public.fish (
      fish_code,
      name,
      nickname,
      genetic_background,
      line_building_stage,
      date_birth,
      description,
      notes,
      created_by
    )
    VALUES (
      public.gen_fish_code(),
      NULLIF(trim(p_name),''),
      NULLIF(trim(p_nickname),''),
      p_genetic_background,
      p_line_building_stage,
      p_date_birth,
      p_description,
      p_notes,
      p_created_by
    )
    RETURNING public.fish.fish_uuid, public.fish.fish_code
      INTO v_fu, v_fc;
  END IF;

  -- D) ensure mapping row (uuid) exists
  INSERT INTO public.fish_seed_batches_map(fish_uuid, seed_batch_id)
  VALUES (v_fu, p_seed_batch_id)
  ON CONFLICT ON CONSTRAINT uq_fsbm_seed_batch_uuid DO NOTHING;

  fish_uuid := v_fu;
  fish_code := v_fc;
  RETURN NEXT;
END
$func$;

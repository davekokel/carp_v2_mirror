-- Drop old version that returned (id, fish_code)
DROP FUNCTION IF EXISTS public.upsert_fish_by_batch_name_dob(
    text, text, date, text, text, text, text, text, text
);

-- Recreate with correct UUID-based signature
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
  v_fish_uuid uuid;
  v_fish_code text;
BEGIN
  SELECT f.fish_uuid, f.fish_code
    INTO v_fish_uuid, v_fish_code
  FROM public.fish f
  JOIN public.fish_seed_batches_map m
    ON m.fish_uuid = f.fish_uuid
   AND m.seed_batch_id = p_seed_batch_id
  WHERE f.name = p_name
    AND f.date_birth = p_date_birth
  LIMIT 1;

  IF v_fish_uuid IS NULL THEN
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
    RETURNING fish_uuid, fish_code INTO v_fish_uuid, v_fish_code;

    INSERT INTO public.fish_seed_batches_map(fish_uuid, seed_batch_id)
    VALUES (v_fish_uuid, p_seed_batch_id);
  END IF;

  RETURN QUERY SELECT v_fish_uuid, v_fish_code;
END
$$;

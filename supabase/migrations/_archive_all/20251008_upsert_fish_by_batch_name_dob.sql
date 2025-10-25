BEGIN;
CREATE UNIQUE INDEX IF NOT EXISTS uq_fsbm_batch_fish
ON public.fish_seed_batches_map (seed_batch_id, fish_id);

CREATE OR REPLACE FUNCTION public.upsert_fish_by_batch_name_dob(
    p_seed_batch_id text,
    p_name text,
    p_date_birth date,
    p_genetic_background text DEFAULT NULL,
    p_nickname text DEFAULT NULL,
    p_line_building_stage text DEFAULT NULL,
    p_description text DEFAULT NULL,
    p_notes text DEFAULT NULL,
    p_created_by text DEFAULT NULL
)
RETURNS TABLE (fish_id uuid, fish_code text) AS
$$
DECLARE
  v_id   uuid;
  v_code text;
BEGIN
  SELECT f.id_uuid, f.fish_code
    INTO v_id, v_code
  FROM public.fish f
  JOIN public.fish_seed_batches_map m
    ON m.fish_id = f.id_uuid
   AND m.seed_batch_id = p_seed_batch_id
  WHERE f.name = p_name
    AND f.date_birth = p_date_birth
  LIMIT 1;

  IF v_id IS NOT NULL THEN
    UPDATE public.fish
       SET name                = COALESCE(p_name, name),
           date_birth          = COALESCE(p_date_birth, date_birth),
           genetic_background  = COALESCE(p_genetic_background, genetic_background),
           nickname            = COALESCE(p_nickname, nickname),
           line_building_stage = COALESCE(p_line_building_stage, line_building_stage),
           description         = COALESCE(p_description, description),
           notes               = COALESCE(p_notes, notes),
           created_by          = COALESCE(p_created_by, created_by)
     WHERE id_uuid = v_id;
    RETURN QUERY SELECT v_id, v_code;
    RETURN;
  END IF;

  INSERT INTO public.fish (
    name, date_birth, genetic_background, nickname,
    line_building_stage, description, notes, created_by
  )
  VALUES (
    p_name, p_date_birth, p_genetic_background, p_nickname,
    p_line_building_stage, p_description, p_notes, p_created_by
  )
  RETURNING id_uuid, fish_code
  INTO v_id, v_code;

  INSERT INTO public.fish_seed_batches_map (fish_id, seed_batch_id)
  VALUES (v_id, p_seed_batch_id)
  ON CONFLICT DO NOTHING;

  RETURN QUERY SELECT v_id, v_code;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp;
COMMIT;

BEGIN;

-- Recreate missing helper: upsert_fish_by_batch_name_dob()
CREATE OR REPLACE FUNCTION public.upsert_fish_by_batch_name_dob(
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
RETURNS TABLE(fish_id uuid, fish_code text)
LANGUAGE plpgsql AS $func$
DECLARE
  v_fish_id uuid;
  v_fish_code text;
BEGIN
  -- ensure code generator exists
  PERFORM 1 FROM pg_proc WHERE proname='to_base36';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'missing dependency: to_base36()';
  END IF;

  -- generate or reuse fish_code
  SELECT id, fish_code INTO v_fish_id, v_fish_code
  FROM public.fish
  WHERE name = p_name
    AND birthday = p_date_birth
    AND seed_batch_id = p_seed_batch_id
  LIMIT 1;

  IF NOT FOUND THEN
    INSERT INTO public.fish (seed_batch_id, name, birthday, genetic_background,
                             nickname, line_building_stage, description, notes,
                             created_by, created_at)
    VALUES (p_seed_batch_id, p_name, p_date_birth, p_genetic_background,
            p_nickname, p_line_building_stage, p_description, p_notes,
            p_created_by::uuid, now())
    RETURNING id, fish_code
    INTO v_fish_id, v_fish_code;
  END IF;

  RETURN QUERY SELECT v_fish_id, v_fish_code;
END
$func$;

COMMIT;

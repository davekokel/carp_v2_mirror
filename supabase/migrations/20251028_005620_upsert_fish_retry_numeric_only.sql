CREATE OR REPLACE FUNCTION public.upsert_fish_by_batch_name_dob(
  p_batch text,
  p_dob date,
  p_seed_batch_id text,
  p_name text,
  p_bg text,
  p_nick text,
  p_stage text,
  p_desc text,
  p_notes text,
  p_by text
)
RETURNS TABLE (fish_uuid uuid, fish_code text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
  v_code text;
  i int := 0;
BEGIN
  <<retry_insert>>
  LOOP
    i := i + 1;
    -- Authoritative numeric code (FSH-YYNNNNN)
    v_code := public.gen_fish_code(now());

    BEGIN
      RETURN QUERY
      INSERT INTO public.fish AS f (
        fish_code, seed_batch_id, name, nickname, genetic_background, line_building_stage,
        date_birth, description, notes, created_by
      )
      VALUES (
        v_code,
        COALESCE(trim(p_seed_batch_id), ''),
        COALESCE(trim(p_name), ''),
        NULLIF(trim(p_nick), ''),
        NULLIF(trim(p_bg), ''),
        NULLIF(trim(p_stage), ''),
        p_dob,
        NULLIF(trim(p_desc), ''),
        NULLIF(trim(p_notes), ''),
        NULLIF(trim(p_by), '')
      )
      ON CONFLICT (seed_batch_id, name, date_birth)
      DO UPDATE SET
        nickname            = COALESCE(EXCLUDED.nickname,            f.nickname),
        genetic_background  = COALESCE(EXCLUDED.genetic_background,  f.genetic_background),
        line_building_stage = COALESCE(EXCLUDED.line_building_stage, f.line_building_stage),
        date_birth          = COALESCE(EXCLUDED.date_birth,          f.date_birth),
        description         = COALESCE(EXCLUDED.description,         f.description),
        notes               = COALESCE(EXCLUDED.notes,               f.notes),
        updated_at          = now()
      RETURNING f.fish_uuid, f.fish_code;

      EXIT; -- success
    EXCEPTION
      WHEN unique_violation THEN
        -- Most likely fish_code collided. Try again a few times.
        IF i < 8 THEN
          CONTINUE retry_insert;
        ELSE
          RAISE EXCEPTION 'Unable to mint unique fish_code after % attempts' USING ERRCODE = '23505';
        END IF;
    END;
  END LOOP;
END
$fn$;

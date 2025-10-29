-- Authoritative upsert: mint fish_code via gen_fish_code(now()),
-- retry on unique_violation of fish_code before giving up.

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
  -- Try to insert with a freshly minted fish_code; if the fish_code already exists,
  -- retry a few times with a new code before giving up.
  <<retry_insert>>
  LOOP
    i := i + 1;
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

      -- Success: exit the retry loop when RETURN QUERY ran.
      EXIT;
    EXCEPTION
      WHEN unique_violation THEN
        -- If the violation was on fish_code, try again with a new code.
        -- We don't parse constraint names here; we just retry a few times.
        IF i < 5 THEN
          CONTINUE retry_insert;
        ELSE
          -- last resort: fall back to a UUID-short code to guarantee uniqueness
          v_code := 'FSH-' || upper(substr(replace(gen_random_uuid()::text,'-',''),1,6));
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
          EXIT;
        END IF;
    END;
  END LOOP;
END
$fn$;

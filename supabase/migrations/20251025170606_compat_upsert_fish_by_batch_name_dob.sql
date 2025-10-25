BEGIN;

-- Create only if the function is missing (local-local baseline)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.proname = 'upsert_fish_by_batch_name_dob'
      AND pg_get_function_identity_arguments(p.oid) =
          'p_seed_batch_id text, p_name text, p_date_birth date, p_genetic_background text, p_nickname text, p_line_building_stage text, p_description text, p_notes text, p_created_by text'
  ) THEN
    CREATE OR REPLACE FUNCTION public.upsert_fish_by_batch_name_dob(
      p_seed_batch_id       text,
      p_name                text,
      p_date_birth          date,
      p_genetic_background  text,
      p_nickname            text,
      p_line_building_stage text,
      p_description         text,
      p_notes               text,
      p_created_by          text
    )
    RETURNS TABLE(fish_id uuid, fish_code text)
    LANGUAGE plpgsql
    AS $func$
    DECLARE
      v_code text;
      v_num  int;
      v_yy   text := to_char(now(), 'YY');
    BEGIN
      -- Mint FSH-YY#### by scanning existing codes for this YY.
      SELECT COALESCE(MAX( (regexp_replace(fish_code, '^FSH-'||v_yy, '')::int) ), 0) + 1
      INTO v_num
      FROM public.fish
      WHERE fish_code ~ ('^FSH-'||v_yy||'\\d{4}$');

      v_code := 'FSH-'||v_yy||lpad(v_num::text, 4, '0');

      INSERT INTO public.fish (
        id, fish_code, name, date_birth, genetic_background, nickname,
        line_building_stage, description, notes, created_by, created_at
      ) VALUES (
        gen_random_uuid(), v_code, NULLIF(p_name,''), p_date_birth, NULLIF(p_genetic_background,''),
        NULLIF(p_nickname,''), NULLIF(p_line_building_stage,''), NULLIF(p_description,''),
        NULLIF(p_notes,''), NULLIF(p_created_by,''), now()
      )
      ON CONFLICT (fish_code) DO UPDATE SET fish_code = EXCLUDED.fish_code
      RETURNING public.fish.id, public.fish.fish_code
      INTO fish_id, fish_code;

      RETURN NEXT;
    END
    $func$;
  END IF;
END$$;

COMMIT;

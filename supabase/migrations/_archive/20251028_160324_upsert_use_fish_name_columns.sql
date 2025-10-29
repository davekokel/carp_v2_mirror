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
BEGIN
  -- Let the BEFORE INSERT trigger mint fish_code (base36); we do NOT set it here
  RETURN QUERY
  INSERT INTO public.fish AS f (
    seed_batch_id, fish_name, fish_nickname, genetic_background, line_building_stage,
    date_birth, description, notes, created_by
  )
  VALUES (
    COALESCE(trim(p_seed_batch_id), ''),
    NULLIF(trim(p_name), ''),
    NULLIF(trim(p_nick), ''),
    NULLIF(trim(p_bg), ''),
    NULLIF(trim(p_stage), ''),
    p_dob,
    NULLIF(trim(p_desc), ''),
    NULLIF(trim(p_notes), ''),
    NULLIF(trim(p_by), '')
  )
  ON CONFLICT (seed_batch_id, name, date_birth)  -- legacy name still in natural key …
  DO UPDATE SET
    fish_nickname       = COALESCE(EXCLUDED.fish_nickname,       f.fish_nickname),
    genetic_background  = COALESCE(EXCLUDED.genetic_background,  f.genetic_background),
    line_building_stage = COALESCE(EXCLUDED.line_building_stage, f.line_building_stage),
    date_birth          = COALESCE(EXCLUDED.date_birth,          f.date_birth),
    description         = COALESCE(EXCLUDED.description,         f.description),
    notes               = COALESCE(EXCLUDED.notes,               f.notes),
    updated_at          = now()
  RETURNING f.fish_uuid, f.fish_code;
END
$fn$;

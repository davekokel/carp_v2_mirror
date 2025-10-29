-- Use ON CONFLICT ON CONSTRAINT to avoid ambiguity with OUT fish_code.
-- Also use RETURN QUERY so callers receive the row.

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
BEGIN
  -- TODO: replace with your real code generator if needed
  v_code := p_batch;

  RETURN QUERY
  INSERT INTO public.fish AS f (
    fish_code, name, nickname, genetic_background, line_building_stage,
    date_birth, description, notes, created_by
  )
  VALUES (
    v_code,
    NULLIF(trim(p_name), ''),
    NULLIF(trim(p_nick), ''),
    NULLIF(trim(p_bg), ''),
    NULLIF(trim(p_stage), ''),
    p_dob,
    NULLIF(trim(p_desc), ''),
    NULLIF(trim(p_notes), ''),
    NULLIF(trim(p_by), '')
  )
  -- IMPORTANT: use named constraint to avoid ambiguity on fish_code
  -- If your unique constraint has a different name, replace fish_fish_code_key below.
  ON CONFLICT ON CONSTRAINT fish_fish_code_key
  DO UPDATE SET
    name                = COALESCE(EXCLUDED.name,                f.name),
    nickname            = COALESCE(EXCLUDED.nickname,            f.nickname),
    genetic_background  = COALESCE(EXCLUDED.genetic_background,  f.genetic_background),
    line_building_stage = COALESCE(EXCLUDED.line_building_stage, f.line_building_stage),
    date_birth          = COALESCE(EXCLUDED.date_birth,          f.date_birth),
    description         = COALESCE(EXCLUDED.description,         f.description),
    notes               = COALESCE(EXCLUDED.notes,               f.notes),
    updated_at          = now()
  RETURNING f.fish_uuid, f.fish_code;
END
$fn$;

-- Make fish import idempotent: use ON CONFLICT (fish_code) DO UPDATE
-- and avoid clobbering existing non-null values with NULLs.

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
RETURNS TABLE (fish_uuid uuid, fish_code text)  -- keep your real return cols
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_code text;
BEGIN
  -- Your code that derives v_code from p_batch/p_seed_batch_id (if any).
  -- If you already have v_code, drop this assignment.
  v_code := p_batch;  -- placeholder: replace with your generator if needed

  INSERT INTO public.fish (
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
  ON CONFLICT (fish_code)
  DO UPDATE SET
    name               = COALESCE(EXCLUDED.name,               public.fish.name),
    nickname           = COALESCE(EXCLUDED.nickname,           public.fish.nickname),
    genetic_background = COALESCE(EXCLUDED.genetic_background, public.fish.genetic_background),
    line_building_stage= COALESCE(EXCLUDED.line_building_stage,public.fish.line_building_stage),
    date_birth         = COALESCE(EXCLUDED.date_birth,         public.fish.date_birth),
    description        = COALESCE(EXCLUDED.description,        public.fish.description),
    notes              = COALESCE(EXCLUDED.notes,              public.fish.notes),
    updated_at         = now()
  WHERE public.fish.fish_code = EXCLUDED.fish_code
  RETURNING public.fish.fish_uuid, public.fish.fish_code
  INTO fish_uuid, fish_code;

  RETURN;
END
$fn$;

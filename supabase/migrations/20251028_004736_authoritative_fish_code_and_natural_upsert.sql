-- 1) Per-year counters and generator: FSH-YYNNNNN (authoritative)
CREATE TABLE IF NOT EXISTS public.fish_year_counters (
  year int PRIMARY KEY,
  next_num int NOT NULL DEFAULT 1
);

CREATE OR REPLACE FUNCTION public.gen_fish_code(p_when timestamptz DEFAULT now())
RETURNS text
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  y  int  := EXTRACT(YEAR FROM p_when)::int;
  yy text := to_char(p_when, 'YY');
  n  int;
BEGIN
  INSERT INTO public.fish_year_counters(year, next_num)
  VALUES (y, 1)
  ON CONFLICT (year) DO NOTHING;

  UPDATE public.fish_year_counters
  SET next_num = next_num + 1
  WHERE year = y
  RETURNING next_num - 1 INTO n;

  RETURN 'FSH-' || yy || to_char(n, 'FM00000');
END
$$;

-- 2) Ensure fish has seed_batch_id for the natural key
ALTER TABLE public.fish
  ADD COLUMN IF NOT EXISTS seed_batch_id text;

-- 3) Natural-key uniqueness: (seed_batch_id, name, date_birth)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint c
    JOIN pg_class rel ON rel.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = rel.relnamespace
    WHERE n.nspname='public' AND rel.relname='fish'
      AND c.contype='u' AND c.conname='uq_fish_seed_name_dob'
  ) THEN
    CREATE UNIQUE INDEX uq_fish_seed_name_dob_idx
      ON public.fish (COALESCE(seed_batch_id,''), COALESCE(name,''), date_birth);
    ALTER TABLE public.fish
      ADD CONSTRAINT uq_fish_seed_name_dob
      UNIQUE USING INDEX uq_fish_seed_name_dob_idx;
  END IF;
END$$;

-- 4) Canonical, idempotent upsert using natural key; mint fish_code on insert only
CREATE OR REPLACE FUNCTION public.upsert_fish_by_batch_name_dob(
  p_batch text,           -- code driver / batch label (stored in seed_batch_id)
  p_dob date,
  p_seed_batch_id text,   -- grouping key (same as p_batch for you today)
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
  -- Authoritative fish_code minting: code assigned only when inserting a new fish
  v_code := public.gen_fish_code(now());

  RETURN QUERY
  INSERT INTO public.fish AS f (
    fish_code, seed_batch_id, name, nickname, genetic_background, line_building_stage,
    date_birth, description, notes, created_by
  )
  VALUES (
    v_code,
    NULLIF(trim(p_seed_batch_id), ''),
    NULLIF(trim(p_name), ''),
    NULLIF(trim(p_nick), ''),
    NULLIF(trim(p_bg), ''),
    NULLIF(trim(p_stage), ''),
    p_dob,
    NULLIF(trim(p_desc), ''),
    NULLIF(trim(p_notes), ''),
    NULLIF(trim(p_by), '')
  )
  ON CONFLICT ON CONSTRAINT uq_fish_seed_name_dob
  DO UPDATE SET
    nickname            = COALESCE(EXCLUDED.nickname,            f.nickname),
    genetic_background  = COALESCE(EXCLUDED.genetic_background,  f.genetic_background),
    line_building_stage = COALESCE(EXCLUDED.line_building_stage, f.line_building_stage),
    date_birth          = COALESCE(EXCLUDED.date_birth,          f.date_birth),  -- keep if provided
    description         = COALESCE(EXCLUDED.description,         f.description),
    notes               = COALESCE(EXCLUDED.notes,               f.notes),
    updated_at          = now()
  RETURNING f.fish_uuid, f.fish_code;
END
$fn$;

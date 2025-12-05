BEGIN;

-- ───────── constructs ─────────
ALTER TABLE public.constructs
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

-- If nickname is missing, fall back to base_code.
UPDATE public.constructs
SET nickname = COALESCE(nickname, base_code)
WHERE nickname IS NULL
   OR nickname = '';

-- display_name prefers human-readable name, then construct_code, then base_code.
UPDATE public.constructs
SET display_name = COALESCE(
    display_name,
    construct_name,
    construct_code,
    base_code
)
WHERE display_name IS NULL
   OR display_name = '';

-- ───────── fluors ─────────
ALTER TABLE public.fluors
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.fluors
SET nickname = COALESCE(nickname, fluor_name, fluor_code)
WHERE nickname IS NULL
   OR nickname = '';

UPDATE public.fluors
SET display_name = COALESCE(display_name, fluor_name, fluor_code)
WHERE display_name IS NULL
   OR display_name = '';

-- ───────── tags ─────────
ALTER TABLE public.tags
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.tags
SET nickname = COALESCE(nickname, tag_name, tag_code)
WHERE nickname IS NULL
   OR nickname = '';

UPDATE public.tags
SET display_name = COALESCE(display_name, tag_name, tag_code)
WHERE display_name IS NULL
   OR display_name = '';

COMMIT;

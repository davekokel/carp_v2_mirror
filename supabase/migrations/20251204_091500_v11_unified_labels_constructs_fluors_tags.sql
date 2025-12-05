BEGIN;

-- ─────────────────────────────────────────────
-- constructs: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.constructs
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.constructs
SET display_name = COALESCE(
    nickname,
    construct_name,
    construct_code,
    base_code
)
WHERE display_name IS NULL;

-- ─────────────────────────────────────────────
-- fluors: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.fluors
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.fluors
SET display_name = COALESCE(
    nickname,
    fluor_name,
    fluor_code
)
WHERE display_name IS NULL;

-- ─────────────────────────────────────────────
-- tags: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.tags
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.tags
SET display_name = COALESCE(
    nickname,
    tag_name,
    tag_code
)
WHERE display_name IS NULL;

COMMIT;

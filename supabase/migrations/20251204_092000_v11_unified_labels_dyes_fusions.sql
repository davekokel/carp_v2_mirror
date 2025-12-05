BEGIN;

-- ─────────────────────────────────────────────
-- dyes: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.dyes
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.dyes
SET display_name = COALESCE(
    nickname,
    name,
    dye_base_code
)
WHERE display_name IS NULL;

-- ─────────────────────────────────────────────
-- fusions: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.fusions
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

-- Build a human-friendly label for fusions:
-- fluor_code::tag_code(tag_pos)
UPDATE public.fusions f
SET display_name = COALESCE(
    f.nickname,
    (
      SELECT
        CONCAT(
          COALESCE(fl.fluor_code, ''),
          CASE
            WHEN fl.fluor_code IS NOT NULL AND tg.tag_code IS NOT NULL THEN '::'
            ELSE ''
          END,
          COALESCE(tg.tag_code, ''),
          CASE
            WHEN f.tag_pos IS NOT NULL AND f.tag_pos <> '' THEN '(' || f.tag_pos || ')'
            ELSE ''
          END
        )
      FROM public.fluors fl
      LEFT JOIN public.tags tg
        ON tg.id = f.tag_id
      WHERE fl.id = f.fluor_id
    )
)
WHERE f.display_name IS NULL;

COMMIT;

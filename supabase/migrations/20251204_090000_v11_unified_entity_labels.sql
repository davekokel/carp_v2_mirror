BEGIN;

-- ─────────────────────────────────────────────
-- fish_groups: add display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.fish_groups
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.fish_groups
SET display_name = COALESCE(nickname, genotype_key, group_code)
WHERE display_name IS NULL;

-- ─────────────────────────────────────────────
-- fish_lines: add display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.fish_lines
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.fish_lines
SET display_name = COALESCE(nickname, line_code)
WHERE display_name IS NULL;

-- ─────────────────────────────────────────────
-- fish_instances_v10: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.fish_instances_v10
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.fish_instances_v10
SET display_name = COALESCE(nickname, fish_code)
WHERE display_name IS NULL;

-- ─────────────────────────────────────────────
-- genotypes_v11: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.genotypes_v11
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.genotypes_v11
SET display_name = COALESCE(nickname, genotype_pretty, genotype_code, genotype_basecodes)
WHERE display_name IS NULL;

-- ─────────────────────────────────────────────
-- transgenes: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.transgenes
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.transgenes
SET display_name = COALESCE(nickname, transgene_name, transgene_base_code)
WHERE display_name IS NULL;

-- ─────────────────────────────────────────────
-- transgene_alleles: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.transgene_alleles
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.transgene_alleles
SET nickname = COALESCE(nickname, allele_nickname, allele_name);

UPDATE public.transgene_alleles
SET display_name = COALESCE(
    nickname,
    allele_nickname,
    allele_name,
    transgene_base_code || ':' || allele_number::text
)
WHERE display_name IS NULL;

-- ─────────────────────────────────────────────
-- treatments: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.treatments
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.treatments
SET nickname = COALESCE(nickname, treat_text);

UPDATE public.treatments
SET display_name = COALESCE(nickname, treat_code)
WHERE display_name IS NULL;

-- ─────────────────────────────────────────────
-- imaging_plates: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.imaging_plates
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.imaging_plates
SET display_name = COALESCE(nickname, plate_code)
WHERE display_name IS NULL;

-- ─────────────────────────────────────────────
-- imaging_slots: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.imaging_slots
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.imaging_slots
SET display_name = COALESCE(nickname, slot_label)
WHERE display_name IS NULL;

-- ─────────────────────────────────────────────
-- imaging_roi_annotations: add nickname + display_name
-- ─────────────────────────────────────────────
ALTER TABLE public.imaging_roi_annotations
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.imaging_roi_annotations
SET display_name = COALESCE(nickname, roi_code)
WHERE display_name IS NULL;

COMMIT;

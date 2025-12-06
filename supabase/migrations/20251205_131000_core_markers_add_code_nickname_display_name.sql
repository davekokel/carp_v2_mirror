BEGIN;

-- ─────────────────────────────────────────────────────
-- Helper: prefix-uuid8 code generator
-- e.g. PREFIX-3f9a7e21
-- ─────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.make_prefixed_code(prefix text, u uuid)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
SELECT prefix || '-' || substring(replace(u::text, '-', '') FROM 1 FOR 8)
$$;

-- ─────────────────────────────────────────────────────
-- DYES
-- ─────────────────────────────────────────────────────
ALTER TABLE public.dyes
  ADD COLUMN IF NOT EXISTS code         text,
  ADD COLUMN IF NOT EXISTS nickname     text,
  ADD COLUMN IF NOT EXISTS display_name text;

-- Ensure id is never NULL (defensive; should already be non-null)
UPDATE public.dyes
SET id = gen_random_uuid()
WHERE id IS NULL;

-- Backfill new fields for existing rows
UPDATE public.dyes
SET code = make_prefixed_code('DYE', id)
WHERE code IS NULL;

UPDATE public.dyes
SET nickname = COALESCE(nickname, dye_base_code, name)
WHERE nickname IS NULL;

UPDATE public.dyes
SET display_name = COALESCE(display_name, name, nickname, code)
WHERE display_name IS NULL;

-- Trigger to populate on INSERT
CREATE OR REPLACE FUNCTION public.dyes_set_code_defaults()
RETURNS trigger AS $$
BEGIN
  IF NEW.id IS NULL THEN
    NEW.id := gen_random_uuid();
  END IF;

  IF NEW.code IS NULL THEN
    NEW.code := public.make_prefixed_code('DYE', NEW.id);
  END IF;

  IF NEW.nickname IS NULL THEN
    NEW.nickname := COALESCE(NEW.dye_base_code, NEW.name);
  END IF;

  IF NEW.display_name IS NULL THEN
    NEW.display_name := COALESCE(NEW.name, NEW.nickname, NEW.code);
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dyes_set_code_defaults ON public.dyes;

CREATE TRIGGER trg_dyes_set_code_defaults
BEFORE INSERT ON public.dyes
FOR EACH ROW
EXECUTE FUNCTION public.dyes_set_code_defaults();

ALTER TABLE public.dyes
  ALTER COLUMN code SET NOT NULL;

ALTER TABLE public.dyes
  ADD CONSTRAINT dyes_code_key UNIQUE (code);

ALTER TABLE public.dyes
  ALTER COLUMN display_name SET NOT NULL;

-- ─────────────────────────────────────────────────────
-- FLUORS
-- ─────────────────────────────────────────────────────
ALTER TABLE public.fluors
  ADD COLUMN IF NOT EXISTS code         text,
  ADD COLUMN IF NOT EXISTS nickname     text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.fluors
SET id = gen_random_uuid()
WHERE id IS NULL;

UPDATE public.fluors
SET code = make_prefixed_code('FLUOR', id)
WHERE code IS NULL;

UPDATE public.fluors
SET nickname = COALESCE(nickname, fluor_code, fluor_name)
WHERE nickname IS NULL;

UPDATE public.fluors
SET display_name = COALESCE(display_name, fluor_name, nickname, code)
WHERE display_name IS NULL;

CREATE OR REPLACE FUNCTION public.fluors_set_code_defaults()
RETURNS trigger AS $$
BEGIN
  IF NEW.id IS NULL THEN
    NEW.id := gen_random_uuid();
  END IF;

  IF NEW.code IS NULL THEN
    NEW.code := public.make_prefixed_code('FLUOR', NEW.id);
  END IF;

  IF NEW.nickname IS NULL THEN
    NEW.nickname := COALESCE(NEW.fluor_code, NEW.fluor_name);
  END IF;

  IF NEW.display_name IS NULL THEN
    NEW.display_name := COALESCE(NEW.fluor_name, NEW.nickname, NEW.code);
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_fluors_set_code_defaults ON public.fluors;

CREATE TRIGGER trg_fluors_set_code_defaults
BEFORE INSERT ON public.fluors
FOR EACH ROW
EXECUTE FUNCTION public.fluors_set_code_defaults();

ALTER TABLE public.fluors
  ALTER COLUMN code SET NOT NULL;

ALTER TABLE public.fluors
  ADD CONSTRAINT fluors_code_key UNIQUE (code);

ALTER TABLE public.fluors
  ALTER COLUMN display_name SET NOT NULL;

-- ─────────────────────────────────────────────────────
-- TAGS
-- ─────────────────────────────────────────────────────
ALTER TABLE public.tags
  ADD COLUMN IF NOT EXISTS code         text,
  ADD COLUMN IF NOT EXISTS nickname     text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.tags
SET id = gen_random_uuid()
WHERE id IS NULL;

UPDATE public.tags
SET code = make_prefixed_code('TAG', id)
WHERE code IS NULL;

UPDATE public.tags
SET nickname = COALESCE(nickname, tag_code, tag_name)
WHERE nickname IS NULL;

UPDATE public.tags
SET display_name = COALESCE(display_name, tag_name, nickname, code)
WHERE display_name IS NULL;

CREATE OR REPLACE FUNCTION public.tags_set_code_defaults()
RETURNS trigger AS $$
BEGIN
  IF NEW.id IS NULL THEN
    NEW.id := gen_random_uuid();
  END IF;

  IF NEW.code IS NULL THEN
    NEW.code := public.make_prefixed_code('TAG', NEW.id);
  END IF;

  IF NEW.nickname IS NULL THEN
    NEW.nickname := COALESCE(NEW.tag_code, NEW.tag_name);
  END IF;

  IF NEW.display_name IS NULL THEN
    NEW.display_name := COALESCE(NEW.tag_name, NEW.nickname, NEW.code);
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tags_set_code_defaults ON public.tags;

CREATE TRIGGER trg_tags_set_code_defaults
BEFORE INSERT ON public.tags
FOR EACH ROW
EXECUTE FUNCTION public.tags_set_code_defaults();

ALTER TABLE public.tags
  ALTER COLUMN code SET NOT NULL;

ALTER TABLE public.tags
  ADD CONSTRAINT tags_code_key UNIQUE (code);

ALTER TABLE public.tags
  ALTER COLUMN display_name SET NOT NULL;

-- ─────────────────────────────────────────────────────
-- CONSTRUCTS
-- ─────────────────────────────────────────────────────
ALTER TABLE public.constructs
  ADD COLUMN IF NOT EXISTS code         text,
  ADD COLUMN IF NOT EXISTS nickname     text,
  ADD COLUMN IF NOT EXISTS display_name text;

UPDATE public.constructs
SET id = gen_random_uuid()
WHERE id IS NULL;

UPDATE public.constructs
SET code = make_prefixed_code('CONSTR', id)
WHERE code IS NULL;

UPDATE public.constructs
SET nickname = COALESCE(nickname, construct_code, construct_name)
WHERE nickname IS NULL;

UPDATE public.constructs
SET display_name = COALESCE(display_name, construct_name, nickname, code)
WHERE display_name IS NULL;

CREATE OR REPLACE FUNCTION public.constructs_set_code_defaults()
RETURNS trigger AS $$
BEGIN
  IF NEW.id IS NULL THEN
    NEW.id := gen_random_uuid();
  END IF;

  IF NEW.code IS NULL THEN
    NEW.code := public.make_prefixed_code('CONSTR', NEW.id);
  END IF;

  IF NEW.nickname IS NULL THEN
    NEW.nickname := COALESCE(NEW.construct_code, NEW.construct_name);
  END IF;

  IF NEW.display_name IS NULL THEN
    NEW.display_name := COALESCE(NEW.construct_name, NEW.nickname, NEW.code);
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_constructs_set_code_defaults ON public.constructs;

CREATE TRIGGER trg_constructs_set_code_defaults
BEFORE INSERT ON public.constructs
FOR EACH ROW
EXECUTE FUNCTION public.constructs_set_code_defaults();

ALTER TABLE public.constructs
  ALTER COLUMN code SET NOT NULL;

ALTER TABLE public.constructs
  ADD CONSTRAINT constructs_code_key UNIQUE (code);

ALTER TABLE public.constructs
  ALTER COLUMN display_name SET NOT NULL;

COMMIT;

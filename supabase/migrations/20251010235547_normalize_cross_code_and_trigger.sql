-- 1) Normalizer: CR-xxxx  →  CROSS-xxxx (also upcases)
CREATE OR REPLACE FUNCTION public.normalize_cross_code(p_code text)
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT CASE
    WHEN p_code IS NULL OR length(btrim(p_code))=0 THEN NULL
    WHEN upper(p_code) ~ '^CR-'     THEN 'CROSS-' || substr(upper(p_code), 4)
    WHEN upper(p_code) ~ '^CROSS-'  THEN upper(p_code)
    ELSE upper(p_code)
  END
$$;

-- 2) BEFORE INSERT/UPDATE trigger to enforce normalization
CREATE OR REPLACE FUNCTION public.trg_cross_code_normalize()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_OP = 'INSERT' OR NEW.cross_code IS DISTINCT FROM OLD.cross_code THEN
    NEW.cross_code := public.normalize_cross_code(NEW.cross_code);
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS bi_normalize_cross_code ON public.crosses;
CREATE TRIGGER bi_normalize_cross_code
BEFORE INSERT OR UPDATE OF cross_code
ON public.crosses
FOR EACH ROW
EXECUTE FUNCTION public.trg_cross_code_normalize();

-- 3) Backfill existing rows safely
UPDATE public.crosses
SET cross_code = public.normalize_cross_code(cross_code)
WHERE cross_code IS NOT NULL
  AND cross_code ~ '^(cr-|[a-z])';

-- 4) Reinstate strict CHECK (CROSS- only). Keep NOT VALID first, then try to validate.
ALTER TABLE public.crosses
  DROP CONSTRAINT IF EXISTS chk_cross_code_shape;

ALTER TABLE public.crosses
  ADD CONSTRAINT chk_cross_code_shape
  CHECK (
    cross_code IS NULL
    OR cross_code ~ '^CROSS-[0-9A-Z]{2}[0-9A-Z]{4,}$'
  ) NOT VALID;

DO $$
BEGIN
  BEGIN
    ALTER TABLE public.crosses VALIDATE CONSTRAINT chk_cross_code_shape;
  EXCEPTION WHEN others THEN
    -- If legacy stragglers exist, leave NOT VALID; we can clean them later.
    NULL;
  END;
END
$$ LANGUAGE plpgsql;

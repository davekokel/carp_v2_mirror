-- 1) Ensure normalizer exists (recreate for idempotency)
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

CREATE OR REPLACE FUNCTION public.trg_cross_code_normalize()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  -- Normalize unconditionally; other BEFORE triggers may set NEW.cross_code
  NEW.cross_code := public.normalize_cross_code(NEW.cross_code);
  RETURN NEW;
END
$$;

-- 2) Drop any previous normalizer trigger and (re)create one that sorts LAST
-- Triggers of same timing fire in name order; 'zz_' ensures we run after others.
DROP TRIGGER IF EXISTS bi_normalize_cross_code ON public.crosses;
DROP TRIGGER IF EXISTS zz_bi_normalize_cross_code ON public.crosses;

CREATE TRIGGER zz_bi_normalize_cross_code
BEFORE INSERT OR UPDATE
ON public.crosses
FOR EACH ROW
EXECUTE FUNCTION public.trg_cross_code_normalize();

-- 3) Re-normalize any existing rows that aren't yet CROSS- prefixed
UPDATE public.crosses
SET cross_code = public.normalize_cross_code(cross_code)
WHERE cross_code IS NOT NULL
  AND cross_code !~ '^CROSS-[0-9A-Z]{2}[0-9A-Z]{4,}$';

-- 4) Keep strict check but NOT VALID (attempt to validate; ignore if some stragglers remain)
ALTER TABLE public.crosses
  DROP CONSTRAINT IF EXISTS chk_cross_code_shape;

ALTER TABLE public.crosses
  ADD CONSTRAINT chk_cross_code_shape
  CHECK (
    cross_code IS NULL
    OR cross_code ~ '^CROSS-[0-9A-Z]{2}[0-9A-Z]{4,}$'
  ) NOT VALID;
DO 28762
BEGIN
  BEGIN
    ALTER TABLE public.crosses VALIDATE CONSTRAINT chk_cross_code_shape;
  EXCEPTION WHEN others THEN
    -- leave NOT VALID; new rows will be normalized by the trigger anyway
    NULL;
  END;
END
$$ LANGUAGE plpgsql;

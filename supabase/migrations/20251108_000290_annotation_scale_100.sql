BEGIN;

-- Intensity / frequency kind codes we care about
WITH kinds AS (
  SELECT id, kind_code
  FROM public.annotations
  WHERE kind_code IN ('red_intensity','green_intensity','red_frequency','green_frequency')
),

-- 1) Backfill: convert legacy 0..1 values to 1..100 (skip NULLs and values already > 1)
upd AS (
  UPDATE public.join_annotations ja
  SET value_num = ROUND(ja.value_num * 100.0, 2)
  FROM kinds k
  WHERE ja.annotation_id = k.id
    AND ja.value_num IS NOT NULL
    AND ja.value_num >= 0 AND ja.value_num <= 1
  RETURNING ja.id
)
SELECT 1;  -- no-op to terminate CTE scope

-- 2) Guard: BEFORE INSERT/UPDATE trigger to normalize inputs
CREATE OR REPLACE FUNCTION public.ja_biu_enforce_scale_100()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_kind text;
BEGIN
  -- Only enforce for our 4 kinds
  SELECT kind_code INTO v_kind
  FROM public.annotations
  WHERE id = NEW.annotation_id
  LIMIT 1;

  IF v_kind IN ('red_intensity','green_intensity','red_frequency','green_frequency') THEN
    IF NEW.value_num IS NULL THEN
      RETURN NEW;
    END IF;

    -- If someone submits 0..1, auto-scale to 1..100
    IF NEW.value_num >= 0 AND NEW.value_num <= 1 THEN
      NEW.value_num := NEW.value_num * 100.0;
    END IF;

    -- Clamp into 1..100 band (allow 0 only if specifically desired; here we normalize 0→1)
    IF NEW.value_num < 1 THEN
      NEW.value_num := 1;
    ELSIF NEW.value_num > 100 THEN
      NEW.value_num := 100;
    END IF;

    -- Optionally round to integer; comment out if you want decimals
    NEW.value_num := ROUND(NEW.value_num);
  END IF;

  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_ja_biu_enforce_scale_100 ON public.join_annotations;
CREATE TRIGGER trg_ja_biu_enforce_scale_100
BEFORE INSERT OR UPDATE ON public.join_annotations
FOR EACH ROW EXECUTE FUNCTION public.ja_biu_enforce_scale_100();

COMMIT;

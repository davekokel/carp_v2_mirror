BEGIN;

-- 0) Preconditions: ensure columns we rely on exist (create if missing)
ALTER TABLE public.clutch_instances
  ADD COLUMN IF NOT EXISTS clutch_genotype_pretty text,
  ADD COLUMN IF NOT EXISTS treatments_genotype_rollup text;

-- 1) Deterministic recompute function (no fallback; requires both inputs)
CREATE OR REPLACE FUNCTION public.clutch_rollup_recompute(p_ci uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  v_gen   text;
  v_treat text;
BEGIN
  -- genotype from clutch_instances (must be non-empty)
  SELECT NULLIF(trim(ci.clutch_genotype_pretty),'')
    INTO v_gen
  FROM public.clutch_instances ci
  WHERE ci.id = p_ci;

  -- treatments pretty from clutch_instance_treatments (distinct codes, newest first)
  SELECT NULLIF(string_agg(DISTINCT t.material_code, ' + ' ORDER BY max(t.created_at) DESC),'')
    INTO v_treat
  FROM public.clutch_instance_treatments t
  WHERE t.clutch_instance_id = p_ci
  GROUP BY t.clutch_instance_id;

  IF v_gen IS NULL OR v_treat IS NULL THEN
    RAISE EXCEPTION 'Cannot compute rollup: need both treatments and genotype (ci=%)', p_ci;
  END IF;

  UPDATE public.clutch_instances
  SET treatments_genotype_rollup = v_treat || ' > ' || v_gen,
      updated_at = COALESCE(updated_at, now())
  WHERE id = p_ci;
END
$$;

-- 2) AFTER triggers to recompute when inputs change
-- 2a) When genotype changes on clutch_instances
CREATE OR REPLACE FUNCTION public.trg_ci_rollup_after_ci()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.clutch_genotype_pretty IS DISTINCT FROM OLD.clutch_genotype_pretty THEN
    PERFORM public.clutch_rollup_recompute(NEW.id);
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_ci_rollup_after_ci ON public.clutch_instances;
CREATE TRIGGER trg_ci_rollup_after_ci
AFTER UPDATE OF clutch_genotype_pretty ON public.clutch_instances
FOR EACH ROW EXECUTE FUNCTION public.trg_ci_rollup_after_ci();

-- 2b) When treatments change on clutch_instance_treatments
CREATE OR REPLACE FUNCTION public.trg_ci_rollup_after_treatment()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  PERFORM public.clutch_rollup_recompute(
    COALESCE(NEW.clutch_instance_id, OLD.clutch_instance_id)
  );
  RETURN COALESCE(NEW, OLD);
END $$;

DROP TRIGGER IF EXISTS trg_ci_rollup_after_treatment_i ON public.clutch_instance_treatments;
CREATE TRIGGER trg_ci_rollup_after_treatment_i
AFTER INSERT ON public.clutch_instance_treatments
FOR EACH ROW EXECUTE FUNCTION public.trg_ci_rollup_after_treatment();

DROP TRIGGER IF EXISTS trg_ci_rollup_after_treatment_u ON public.clutch_instance_treatments;
CREATE TRIGGER trg_ci_rollup_after_treatment_u
AFTER UPDATE OF material_type, material_code, material_name ON public.clutch_instance_treatments
FOR EACH ROW EXECUTE FUNCTION public.trg_ci_rollup_after_treatment();

DROP TRIGGER IF EXISTS trg_ci_rollup_after_treatment_d ON public.clutch_instance_treatments;
CREATE TRIGGER trg_ci_rollup_after_treatment_d
AFTER DELETE ON public.clutch_instance_treatments
FOR EACH ROW EXECUTE FUNCTION public.trg_ci_rollup_after_treatment();

-- 3) STRICT enforcement: block writes that would leave rollup absent (no fallback)
-- Use an AFTER CONSTRAINT trigger so NEW.id exists and FK rows can be seen.
CREATE OR REPLACE FUNCTION public.trg_ci_enforce_rollup()
RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  v_gen text;
  v_has_treat boolean;
BEGIN
  SELECT NULLIF(trim(NEW.clutch_genotype_pretty),'') INTO v_gen;
  SELECT EXISTS (
    SELECT 1 FROM public.clutch_instance_treatments t
    WHERE t.clutch_instance_id = NEW.id
  ) INTO v_has_treat;

  IF v_gen IS NULL OR NOT v_has_treat THEN
    RAISE EXCEPTION 'Both genotype and at least one treatment are required (no fallback).';
  END IF;

  -- Compute/store now (guaranteed inputs present)
  PERFORM public.clutch_rollup_recompute(NEW.id);
  RETURN NEW;
END $$;

-- Drop any legacy version and install as an AFTER CONSTRAINT trigger
DROP TRIGGER IF EXISTS trg_ci_enforce_rollup ON public.clutch_instances;
CREATE CONSTRAINT TRIGGER trg_ci_enforce_rollup
AFTER INSERT OR UPDATE OF clutch_genotype_pretty
ON public.clutch_instances
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION public.trg_ci_enforce_rollup();

-- 4) Backfill existing rows that already have both sides
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT ci.id
    FROM public.clutch_instances ci
    WHERE NULLIF(trim(ci.clutch_genotype_pretty),'') IS NOT NULL
      AND EXISTS (SELECT 1 FROM public.clutch_instance_treatments t WHERE t.clutch_instance_id = ci.id)
  LOOP
    BEGIN
      PERFORM public.clutch_rollup_recompute(r.id);
    EXCEPTION WHEN OTHERS THEN
      RAISE NOTICE 'Skipped backfill for CI=% due to: %', r.id, SQLERRM;
    END;
  END LOOP;
END $$;

-- 5) Try to enforce NOT NULL if nothing is missing
DO $$
DECLARE c_missing int;
BEGIN
  SELECT count(*) INTO c_missing
  FROM public.clutch_instances
  WHERE treatments_genotype_rollup IS NULL;

  IF c_missing = 0 THEN
    ALTER TABLE public.clutch_instances
      ALTER COLUMN treatments_genotype_rollup SET NOT NULL;
  ELSE
    RAISE NOTICE 'treatments_genotype_rollup left NULLABLE (% rows missing); future writes are enforced by triggers', c_missing;
  END IF;
END $$;

COMMIT;
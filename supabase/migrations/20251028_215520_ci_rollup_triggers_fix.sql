BEGIN;

-- Ensure recompute function exists (no-op if already defined; update body only if you want)
CREATE OR REPLACE FUNCTION public.clutch_rollup_recompute(p_ci uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  v_gen   text;
  v_treat text;
BEGIN
  SELECT NULLIF(trim(ci.clutch_genotype_pretty),'') INTO v_gen
  FROM public.clutch_instances ci WHERE ci.id = p_ci;

  SELECT string_agg(s.material_code, ' + ' ORDER BY s.max_created_at DESC)
    INTO v_treat
  FROM (
    SELECT material_code, max(created_at) AS max_created_at
    FROM public.clutch_instance_treatments
    WHERE clutch_instance_id = p_ci
    GROUP BY material_code
  ) s;

  UPDATE public.clutch_instances
  SET treatments_genotype_rollup =
        CASE WHEN v_gen IS NOT NULL AND v_treat IS NOT NULL
             THEN v_treat || ' > ' || v_gen
             ELSE NULL
        END,
      updated_at = COALESCE(updated_at, now())
  WHERE id = p_ci;
END
$$;

-- After-treatment trigger fn
CREATE OR REPLACE FUNCTION public.trg_ci_rollup_after_treatment()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  PERFORM public.clutch_rollup_recompute(
    COALESCE(NEW.clutch_instance_id, OLD.clutch_instance_id)
  );
  RETURN COALESCE(NEW, OLD);
END $$;

-- Drop & recreate triggers on the treatments table
DROP TRIGGER IF EXISTS trg_ci_rollup_after_treatment_i ON public.clutch_instance_treatments;
DROP TRIGGER IF EXISTS trg_ci_rollup_after_treatment_u ON public.clutch_instance_treatments;
DROP TRIGGER IF EXISTS trg_ci_rollup_after_treatment_d ON public.clutch_instance_treatments;

CREATE TRIGGER trg_ci_rollup_after_treatment_i
AFTER INSERT ON public.clutch_instance_treatments
FOR EACH ROW EXECUTE FUNCTION public.trg_ci_rollup_after_treatment();

CREATE TRIGGER trg_ci_rollup_after_treatment_u
AFTER UPDATE OF material_type, material_code, material_name ON public.clutch_instance_treatments
FOR EACH ROW EXECUTE FUNCTION public.trg_ci_rollup_after_treatment();

CREATE TRIGGER trg_ci_rollup_after_treatment_d
AFTER DELETE ON public.clutch_instance_treatments
FOR EACH ROW EXECUTE FUNCTION public.trg_ci_rollup_after_treatment();

-- Backfill: recompute for all clutches
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN SELECT id FROM public.clutch_instances LOOP
    PERFORM public.clutch_rollup_recompute(r.id);
  END LOOP;
END $$;

COMMIT;

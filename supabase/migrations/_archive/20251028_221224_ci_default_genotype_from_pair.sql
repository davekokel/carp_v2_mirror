BEGIN;

-- Helper: get the tank_pair_code for this clutch, even if only cross_instance_id is set
CREATE OR REPLACE FUNCTION public._ci_resolve_tp_code(p_ciid uuid, p_tp text)
RETURNS text
LANGUAGE sql
AS $$
  select coalesce(
    nullif(p_tp, ''),
    (select ci.tank_pair_code from public.cross_instances ci where ci.id = p_ciid)
  )
$$;

-- BEFORE INSERT trigger: if no genotype supplied, copy from fish_pairs.genotype_elems
CREATE OR REPLACE FUNCTION public.clutch_default_genotype_from_pair()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_tp   text;
  v_gen  text;
  v_has_elems boolean;
BEGIN
  -- If caller already provided a genotype, keep it
  IF NULLIF(trim(NEW.clutch_genotype_pretty), '') IS NOT NULL THEN
    RETURN NEW;
  END IF;

  v_tp := public._ci_resolve_tp_code(NEW.cross_instance_id, NEW.tank_pair_code);

  IF v_tp IS NULL THEN
    RETURN NEW; -- nothing we can do
  END IF;

  -- Only attempt if fish_pairs has genotype_elems
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish_pairs' AND column_name='genotype_elems'
  ) INTO v_has_elems;

  IF v_has_elems THEN
    SELECT
      NULLIF(array_to_string(fp.genotype_elems, '; '), '')
    INTO v_gen
    FROM public.tank_pairs tp
    JOIN public.fish_pairs fp ON fp.fish_pair_code = tp.fish_pair_code
    WHERE tp.tank_pair_code = v_tp
    LIMIT 1;

    IF v_gen IS NOT NULL THEN
      NEW.clutch_genotype_pretty := v_gen;
    END IF;
  END IF;

  RETURN NEW;
END
$fn$;

-- Install / replace the BEFORE INSERT trigger on clutch_instances
DROP TRIGGER IF EXISTS trg_ci_default_genotype ON public.clutch_instances;
CREATE TRIGGER trg_ci_default_genotype
BEFORE INSERT ON public.clutch_instances
FOR EACH ROW EXECUTE FUNCTION public.clutch_default_genotype_from_pair();

-- One-time backfill: set genotype for existing rows that are missing it
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT ci.id,
           public._ci_resolve_tp_code(ci.cross_instance_id, ci.tank_pair_code) AS tp
    FROM public.clutch_instances ci
    WHERE NULLIF(trim(ci.clutch_genotype_pretty), '') IS NULL
  LOOP
    UPDATE public.clutch_instances x
    SET clutch_genotype_pretty = sub.gen
    FROM (
      SELECT NULLIF(array_to_string(fp.genotype_elems, '; '), '') AS gen
      FROM public.tank_pairs tp
      JOIN public.fish_pairs fp ON fp.fish_pair_code = tp.fish_pair_code
      WHERE tp.tank_pair_code = r.tp
      LIMIT 1
    ) sub
    WHERE x.id = r.id AND sub.gen IS NOT NULL;
  END LOOP;
END $$;

COMMIT;

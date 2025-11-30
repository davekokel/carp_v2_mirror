BEGIN;

CREATE OR REPLACE FUNCTION public.fn_frontfill_clutch_genotype_on_imaging()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_geno_id      uuid;
  v_base_codes   text;
  v_clutch_code  text;
BEGIN
  -- no clutch -> nothing to do
  IF NEW.clutch_id IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT
    genotype_v11_id,
    genotype_base_codes,
    clutch_code
  INTO
    v_geno_id,
    v_base_codes,
    v_clutch_code
  FROM public.clutches
  WHERE id = NEW.clutch_id
  LIMIT 1;

  IF NOT FOUND THEN
    RETURN NEW;
  END IF;

  -- already wired
  IF v_geno_id IS NOT NULL THEN
    RETURN NEW;
  END IF;

  v_base_codes  := COALESCE(TRIM(v_base_codes), '');
  v_clutch_code := COALESCE(TRIM(v_clutch_code), '');

  -- if no genotype_base_codes, fall back to clutch_code
  IF v_base_codes = '' THEN
    v_base_codes := v_clutch_code;
  END IF;

  -- still nothing usable
  IF v_base_codes = '' THEN
    RETURN NEW;
  END IF;

  -- reuse existing genotype_v11 if possible
  SELECT id
  INTO v_geno_id
  FROM public.genotypes_v11
  WHERE genotype_basecodes = v_base_codes
  LIMIT 1;

  -- otherwise create a new genotype_v11 row
  IF v_geno_id IS NULL THEN
    INSERT INTO public.genotypes_v11
      (id, genotype_code, genotype_pretty, genotype_basecodes, created_at)
    VALUES (
      gen_random_uuid(),
      'G-' || UPPER(SUBSTR(md5(v_base_codes), 1, 10)),
      v_base_codes,
      v_base_codes,
      now()
    )
    RETURNING id INTO v_geno_id;
  END IF;

  -- wire the clutch to this genotype
  UPDATE public.clutches
  SET genotype_v11_id = v_geno_id
  WHERE id = NEW.clutch_id;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_frontfill_clutch_genotype_on_imaging
ON public.imaging_clutch_memberships;

CREATE TRIGGER trg_frontfill_clutch_genotype_on_imaging
AFTER INSERT ON public.imaging_clutch_memberships
FOR EACH ROW
EXECUTE FUNCTION public.fn_frontfill_clutch_genotype_on_imaging();

COMMIT;

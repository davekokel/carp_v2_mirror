BEGIN;

-- 1) Add snapshot columns (idempotent)
ALTER TABLE public.tank_pairs
  ADD COLUMN IF NOT EXISTS mom_tank_code text,
  ADD COLUMN IF NOT EXISTS dad_tank_code text,
  ADD COLUMN IF NOT EXISTS mom_genotype  text,
  ADD COLUMN IF NOT EXISTS dad_genotype  text;

COMMENT ON COLUMN public.tank_pairs.mom_tank_code IS 'Tank code of mother at time of pairing (snapshot)';
COMMENT ON COLUMN public.tank_pairs.dad_tank_code IS 'Tank code of father at time of pairing (snapshot)';
COMMENT ON COLUMN public.tank_pairs.mom_genotype  IS 'Genotype string of mother''s fish at time of pairing (snapshot from v_fish.genotype)';
COMMENT ON COLUMN public.tank_pairs.dad_genotype  IS 'Genotype string of father''s fish at time of pairing (snapshot from v_fish.genotype)';

-- 2) Trigger to enrich snapshots on insert/update of tank ids
CREATE OR REPLACE FUNCTION public.tank_pairs_enrich_snapshots()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE
  m_code text; m_fish text; m_geno text;
  d_code text; d_fish text; d_geno text;
BEGIN
  -- mother
  IF NEW.mother_tank_id IS NOT NULL THEN
    SELECT t.tank_code, t.fish_code INTO m_code, m_fish
      FROM public.tanks t WHERE t.tank_id = NEW.mother_tank_id;
    IF m_code IS NOT NULL THEN
      NEW.mom_tank_code := m_code;
    END IF;
    IF m_fish IS NOT NULL THEN
      SELECT v.genotype INTO m_geno FROM public.v_fish v WHERE v.fish_code = m_fish;
      IF m_geno IS NOT NULL THEN
        NEW.mom_genotype := m_geno;
      END IF;
    END IF;
  END IF;

  -- father
  IF NEW.father_tank_id IS NOT NULL THEN
    SELECT t.tank_code, t.fish_code INTO d_code, d_fish
      FROM public.tanks t WHERE t.tank_id = NEW.father_tank_id;
    IF d_code IS NOT NULL THEN
      NEW.dad_tank_code := d_code;
    END IF;
    IF d_fish IS NOT NULL THEN
      SELECT v.genotype INTO d_geno FROM public.v_fish v WHERE v.fish_code = d_fish;
      IF d_geno IS NOT NULL THEN
        NEW.dad_genotype := d_geno;
      END IF;
    END IF;
  END IF;

  RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_tank_pairs_enrich_snapshots ON public.tank_pairs;
CREATE TRIGGER trg_tank_pairs_enrich_snapshots
BEFORE INSERT OR UPDATE OF mother_tank_id, father_tank_id
ON public.tank_pairs
FOR EACH ROW
EXECUTE FUNCTION public.tank_pairs_enrich_snapshots();

-- 3) Backfill any existing rows missing snapshots (best-effort)
UPDATE public.tank_pairs tp
SET
  mom_tank_code = COALESCE(tp.mom_tank_code, mt.tank_code),
  mom_genotype  = COALESCE(tp.mom_genotype , vf.genotype),
  dad_tank_code = COALESCE(tp.dad_tank_code, dt.tank_code),
  dad_genotype  = COALESCE(tp.dad_genotype , vf2.genotype)
FROM public.tanks mt
LEFT JOIN public.v_fish vf  ON vf.fish_code  = mt.fish_code
LEFT JOIN public.tanks dt   ON dt.tank_id    = tp.father_tank_id
LEFT JOIN public.v_fish vf2 ON vf2.fish_code = dt.fish_code
WHERE mt.tank_id = tp.mother_tank_id
  AND (tp.mom_tank_code IS NULL OR tp.mom_genotype IS NULL OR
       tp.dad_tank_code IS NULL OR tp.dad_genotype IS NULL);

COMMIT;

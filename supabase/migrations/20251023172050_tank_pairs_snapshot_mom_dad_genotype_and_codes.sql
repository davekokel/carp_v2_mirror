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

-- 2) Trigger to enrich snapshots on insert/update of tank columns
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
WITH m AS (
  SELECT tp.id,
         tm.tank_code AS m_code,
         vf.genotype  AS m_geno
  FROM public.tank_pairs tp
  LEFT JOIN public.tanks   tm ON tm.tank_id = tp.mother_tank_id
  LEFT JOIN public.v_fish  vf ON vf.fish_code = tm.fish_code
  WHERE (tp.mom_tank_code IS NULL OR tp.mom_genotype IS NULL)
),
d AS (
  SELECT tp.id,
         td.tank_code AS d_code,
         vf2.genotype AS d_geno
  FROM public.tank_pairs tp
  LEFT JOIN public.tanks   td  ON td.tank_id = tp.father_tank_id
  LEFT JOIN public.v_fish  vf2 ON vf2.fish_code = td.fish_code
  WHERE (tp.dad_tank_code IS NULL OR tp.dad_genotype IS NULL)
)
UPDATE public.tank_pairs x
SET mom_tank_code = COALESCE(m.m_code, x.mom_tank_code),
    mom_genotype  = COALESCE(m.m_geno, x.mom_genotype),
    dad_tank_code = COALESCE(d.d_code, x.dad_tank_code),
    dad_genotype  = COALESCE(d.d_geno, x.dad_genotype)
FROM m JOIN d ON d.id = m.id
WHERE x.id = m.id;

-- 4) Expose snapshots via v_tank_pairs (no fish_id join, tanks-only)
CREATE OR REPLACE VIEW public.v_tank_pairs AS
SELECT
  tp.id,
  tp.tank_pair_code,
  tp.status,
  tp.role_orientation,
  tp.concept_id,
  tp.fish_pair_id,
  tp.created_by,
  tp.created_at,
  tp.updated_at,

  -- mother side
  mt.tank_id   AS mother_tank_id,
  COALESCE(tp.mom_tank_code, mt.tank_code) AS mom_tank_code,
  mt.fish_code AS mom_fish_code,
  tp.mom_genotype,

  -- father side
  dt.tank_id   AS father_tank_id,
  COALESCE(tp.dad_tank_code, dt.tank_code) AS dad_tank_code,
  dt.fish_code AS dad_fish_code,
  tp.dad_genotype

FROM public.tank_pairs tp
LEFT JOIN public.tanks mt ON mt.tank_id = tp.mother_tank_id
LEFT JOIN public.tanks dt ON dt.tank_id = tp.father_tank_id
ORDER BY tp.created_at DESC NULLS LAST;

COMMIT;

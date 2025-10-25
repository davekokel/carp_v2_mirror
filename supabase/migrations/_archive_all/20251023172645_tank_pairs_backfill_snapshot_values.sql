BEGIN;

WITH snap AS (
  SELECT
    tp.id                                           AS tp_id,
    mt.tank_code                                    AS m_code,
    vf.genotype                                     AS m_geno,
    dt.tank_code                                    AS d_code,
    vf2.genotype                                    AS d_geno
  FROM public.tank_pairs tp
  LEFT JOIN public.tanks   mt  ON mt.tank_id    = tp.mother_tank_id
  LEFT JOIN public.v_fish  vf  ON vf.fish_code  = mt.fish_code
  LEFT JOIN public.tanks   dt  ON dt.tank_id    = tp.father_tank_id
  LEFT JOIN public.v_fish  vf2 ON vf2.fish_code = dt.fish_code
)
UPDATE public.tank_pairs AS tp
SET
  mom_tank_code = COALESCE(tp.mom_tank_code, s.m_code),
  mom_genotype  = COALESCE(tp.mom_genotype , s.m_geno),
  dad_tank_code = COALESCE(tp.dad_tank_code, s.d_code),
  dad_genotype  = COALESCE(tp.dad_genotype , s.d_geno)
FROM snap AS s
WHERE s.tp_id = tp.id
  AND (
    tp.mom_tank_code IS NULL OR tp.mom_genotype IS NULL OR
    tp.dad_tank_code IS NULL OR tp.dad_genotype IS NULL
  );

COMMIT;

BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_star CASCADE;

CREATE VIEW public.v11_clutch_star AS
SELECT
    c.id                       AS clutch_id,
    c.clutch_code,
    c.clutch_date,
    c.estimated_egg_count,
    c.notes,
    c.created_at,

    -- v11 genotype assignment
    c.genotype_v11_id,
    g.genotype_code,
    g.genotype_pretty,
    g.genotype_basecodes,

    -- treatments (0, 1, or many)
    jt.treatment_id,
    t.treat_code,
    t.treat_text

FROM public.clutches c
LEFT JOIN public.genotypes_v11 g
  ON g.id = c.genotype_v11_id

LEFT JOIN public.join_clutch_treatments jt
  ON jt.clutch_id = c.id

LEFT JOIN public.treatments t
  ON t.id = jt.treatment_id;

COMMENT ON VIEW public.v11_clutch_star IS
  'v11 clutch star: clutches + genotype_v11 + treatments';

COMMIT;

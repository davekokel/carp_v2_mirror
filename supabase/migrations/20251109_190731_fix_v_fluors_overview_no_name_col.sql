BEGIN;

CREATE OR REPLACE VIEW public.v_fluors_overview AS
WITH u AS (
  SELECT
    fl.id,
    fl.fluor_code,
    fl.excitation_nm,
    fl.emission_nm,
    COALESCE(fl.notes,'') AS notes,
    fl.created_at
  FROM public.fluors fl
),
cnt AS (
  SELECT
    u.id,
    COUNT(DISTINCT f.id)            AS n_fusions,
    COUNT(DISTINCT jpf.plasmid_id)  AS n_plasmids
  FROM u
  LEFT JOIN public.fusions f              ON f.fluor_id = u.id
  LEFT JOIN public.join_plasmid_fusions jpf ON jpf.fusion_id = f.id
  GROUP BY u.id
)
SELECT
  u.fluor_code,
  u.fluor_code                  AS name,          -- no fl.name column; use code as display
  u.excitation_nm,
  u.emission_nm,
  u.notes,
  COALESCE(cnt.n_fusions,0)     AS n_fusions,
  COALESCE(cnt.n_plasmids,0)    AS n_plasmids,
  u.created_at
FROM u
LEFT JOIN cnt ON cnt.id = u.id;

COMMIT;
